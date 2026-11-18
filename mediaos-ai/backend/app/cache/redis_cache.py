"""Redis keş qatı.

Prinsiplər:
  * Redis yalnız sürət qatıdır. Hər əməliyyat xətaya dözümlüdür: Redis əlçatmaz olsa,
    `get` None qaytarır, `set` heç nə etmir və çağıran kod PostgreSQL-dən oxuyur.
  * Circuit breaker: ardıcıl xətadan sonra Redis `cooldown` müddətinə söndürülür ki,
    hər sorğu timeout gözləməsin.
  * İnvalidasiya namespace versiyası ilə edilir: `invalidate("dashboard")` versiyanı artırır,
    köhnə açarlar TTL bitənə qədər yaddaşda qalır, amma heç vaxt oxunmur (KEYS/SCAN lazım deyil).
  * Əhatə (scope): "public" (hamı üçün eyni), "role:<rol>" (icazədən asılı nəticə),
    "user:<id>" (şəxsi). Şəxsi məlumat heç vaxt public açarla yazılmır.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import redis

from app.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T")
PREFIX = "mos"


@dataclass
class CacheStats:
    hits: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    misses: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors: int = 0
    bypass: int = 0

    def snapshot(self) -> dict[str, Any]:
        namespaces = sorted(set(self.hits) | set(self.misses))
        per_ns = {}
        for ns in namespaces:
            h, m = self.hits[ns], self.misses[ns]
            per_ns[ns] = {"hits": h, "misses": m, "hit_rate": round(h / (h + m), 4) if h + m else None}
        th, tm = sum(self.hits.values()), sum(self.misses.values())
        return {
            "hits": th,
            "misses": tm,
            "hit_rate": round(th / (th + tm), 4) if th + tm else None,
            "errors": self.errors,
            "bypass_while_down": self.bypass,
            "namespaces": per_ns,
        }


def make_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class RedisCache:
    def __init__(self, url: str | None = None, cooldown_s: float = 5.0):
        s = get_settings()
        self._url = url or s.redis_url
        self._client = redis.Redis.from_url(
            self._url,
            socket_timeout=s.redis_socket_timeout,
            socket_connect_timeout=s.redis_socket_timeout,
            decode_responses=True,
        )
        self._cooldown_s = cooldown_s
        self._down_until = 0.0
        self._lock = threading.Lock()
        self.stats = CacheStats()
        # Redis düşəndə rate limit üçün proses daxili ehtiyat sayğac
        self._local_rl: dict[str, tuple[int, int]] = {}

    # ---------------- daxili ----------------
    @property
    def available(self) -> bool:
        return time.monotonic() >= self._down_until

    def _fail(self, exc: Exception) -> None:
        with self._lock:
            self.stats.errors += 1
            self._down_until = time.monotonic() + self._cooldown_s
        log.warning("Redis əlçatmazdır, %ss PostgreSQL rejiminə keçilir: %s", self._cooldown_s, exc)

    def _call(self, fn: Callable[[], T], default: T) -> T:
        if not self.available:
            self.stats.bypass += 1
            return default
        try:
            return fn()
        except redis.RedisError as exc:
            self._fail(exc)
            return default

    def _ns_version(self, ns: str) -> str:
        v = self._call(lambda: self._client.get(f"{PREFIX}:nsv:{ns}"), None)
        return v or "0"

    def _full_key(self, ns: str, scope: str, key: str) -> str:
        return f"{PREFIX}:{ns}:v{self._ns_version(ns)}:{scope}:{key}"

    # ---------------- ictimai API ----------------
    def get(self, ns: str, key: str, scope: str = "public") -> Any | None:
        if not self.available:
            self.stats.bypass += 1
            return None
        raw = self._call(lambda: self._client.get(self._full_key(ns, scope, key)), None)
        if raw is None:
            self.stats.misses[ns] += 1
            self._call(lambda: self._client.hincrby(f"{PREFIX}:stats", f"{ns}:miss", 1), None)
            return None
        self.stats.hits[ns] += 1
        self._call(lambda: self._client.hincrby(f"{PREFIX}:stats", f"{ns}:hit", 1), None)
        return json.loads(raw)

    def set(self, ns: str, key: str, value: Any, ttl: int, scope: str = "public") -> bool:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        return bool(self._call(lambda: self._client.set(self._full_key(ns, scope, key), payload, ex=ttl), False))

    def get_or_set(self, ns: str, key: str, ttl: int, loader: Callable[[], T], scope: str = "public") -> tuple[T, str]:
        """(dəyər, 'hit'|'miss'|'bypass') qaytarır. Loader həmişə PostgreSQL-dən oxuyur."""
        if not self.available:
            self.stats.bypass += 1
            return loader(), "bypass"
        cached = self.get(ns, key, scope)
        if cached is not None:
            return cached, "hit"
        value = loader()
        self.set(ns, key, value, ttl, scope)
        return value, ("miss" if self.available else "bypass")

    def invalidate(self, ns: str) -> None:
        self._call(lambda: self._client.incr(f"{PREFIX}:nsv:{ns}"), None)

    def delete_scope(self, ns: str, scope: str) -> int:
        """Bir istifadəçinin keşini silir (məs. yaddaş silinəndə)."""
        def _do() -> int:
            n = 0
            for k in self._client.scan_iter(match=f"{PREFIX}:{ns}:v*:{scope}:*", count=500):
                n += self._client.delete(k)
            return n
        return self._call(_do, 0)

    # ---------------- rate limiting ----------------
    def rate_limit(self, bucket: str, limit: int, window_s: int = 60) -> tuple[bool, int]:
        """Sabit pəncərə limiti. (icazə, qalan) qaytarır. Redis düşsə proses daxili sayğac işləyir."""
        window = int(time.time() // window_s)
        key = f"{PREFIX}:rl:{bucket}:{window}"

        def _redis() -> int:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_s + 1)
            return int(pipe.execute()[0])

        count = self._call(_redis, -1)
        if count == -1:
            with self._lock:
                w, c = self._local_rl.get(bucket, (window, 0))
                c = c + 1 if w == window else 1
                self._local_rl[bucket] = (window, c)
                count = c
        return count <= limit, max(0, limit - count)

    # ---------------- monitorinq ----------------
    def info(self) -> dict[str, Any]:
        def _info() -> dict[str, Any]:
            mem = self._client.info("memory")
            stats = self._client.info("stats")
            cfg = self._client.config_get("maxmemory*")
            persisted = self._client.hgetall(f"{PREFIX}:stats")
            return {
                "up": True,
                "used_memory_human": mem.get("used_memory_human"),
                "maxmemory": int(cfg.get("maxmemory", 0)),
                "maxmemory_policy": cfg.get("maxmemory-policy"),
                "evicted_keys": stats.get("evicted_keys"),
                "server_keyspace_hits": stats.get("keyspace_hits"),
                "server_keyspace_misses": stats.get("keyspace_misses"),
                "persisted_counters": persisted,
            }
        data = self._call(_info, {"up": False})
        data["process"] = self.stats.snapshot()
        return data

    def ping(self) -> bool:
        return bool(self._call(lambda: self._client.ping(), False))


_cache: RedisCache | None = None


def get_cache() -> RedisCache:
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache


def set_cache(c: RedisCache | None) -> None:
    global _cache
    _cache = c
