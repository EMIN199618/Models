"""1. Redis Caching — keş, invalidasiya, izolyasiya, rate limit, Redis nasaz olduqda davamlılıq."""
import uuid
from datetime import datetime, timezone

from app.cache.redis_cache import RedisCache, get_cache
from tests.conftest import auth


def test_get_or_set_hit_miss_and_invalidation():
    c = get_cache()
    ns = f"t{uuid.uuid4().hex[:6]}"
    calls = []
    loader = lambda: calls.append(1) or {"v": len(calls)}  # noqa: E731
    v1, s1 = c.get_or_set(ns, "k", 30, loader)
    v2, s2 = c.get_or_set(ns, "k", 30, loader)
    assert (s1, s2) == ("miss", "hit") and v1 == v2 and len(calls) == 1
    c.invalidate(ns)
    _, s3 = c.get_or_set(ns, "k", 30, loader)
    assert s3 == "miss" and len(calls) == 2


def test_ttl_is_applied():
    c = get_cache()
    c.set("ttl", "k", {"a": 1}, ttl=7)
    key = c._full_key("ttl", "public", "k")
    assert 0 < c._client.ttl(key) <= 7


def test_user_scopes_are_isolated():
    c = get_cache()
    c.set("ai_answer", "same-question", {"answer": "user1 private"}, 60, scope="user:1")
    assert c.get("ai_answer", "same-question", scope="user:2") is None
    assert c.get("ai_answer", "same-question", scope="user:1")["answer"] == "user1 private"


def test_rate_limit_redis_and_local_fallback(redis_down):
    ok = RedisCache()
    b = f"rl-{uuid.uuid4().hex[:6]}"
    res = [ok.rate_limit(b, 3)[0] for _ in range(5)]
    assert res == [True, True, True, False, False]
    # Redis düşəndə proses daxili limit işləyir
    res2 = [redis_down.rate_limit(b, 2)[0] for _ in range(3)]
    assert res2 == [True, True, False]


def test_redis_down_falls_back_to_postgres(redis_down, client):
    r = client.get("/api/dashboard/stats?days=30", headers=auth("viewer"))
    assert r.status_code == 200
    assert r.headers["X-Cache"] == "bypass"
    assert r.json()["total"] > 0
    r2 = client.get("/api/news/latest?limit=5", headers=auth("viewer"))
    assert r2.status_code == 200 and len(r2.json()) == 5
    assert redis_down.stats.bypass >= 2


def test_dashboard_cache_and_invalidation_on_new_data(client):
    get_cache().invalidate("dashboard")
    h = auth("analyst")
    assert client.get("/api/dashboard/stats?days=7", headers=h).headers["X-Cache"] == "miss"
    assert client.get("/api/dashboard/stats?days=7", headers=h).headers["X-Cache"] == "hit"
    r = client.post("/api/ingest/news", headers=auth("admin"), json=[{
        "source_name": "Test mənbə (nümunə)", "source_kind": "media",
        "title": "Dövlət Gömrük Komitəsi yeni gömrük postu açıb (test)",
        "body": "Dövlət Gömrük Komitəsi Horadiz gömrük postunda yeni terminal açıb. Test məlumatıdır.",
        "published_at": datetime.now(timezone.utc).isoformat()}])
    assert r.status_code == 200 and r.json()["relevant"] == 1
    assert client.get("/api/dashboard/stats?days=7", headers=h).headers["X-Cache"] == "miss"


def test_cache_info_reports_policy_and_hit_rate():
    info = get_cache().info()
    assert info["up"] is True
    assert info["maxmemory_policy"] in ("allkeys-lru", "volatile-lru", "allkeys-lfu", "noeviction", "volatile-ttl")
    assert "hit_rate" in info["process"]
