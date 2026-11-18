"""EnsembleData inteqrasiyası: TikTok və Instagram-dan DGK ilə bağlı paylaşımların toplanması.

Mənbələr:
  TikTok    — açar söz axtarışı (/tt/keyword/search), heşteq (/tt/hashtag/posts), hesab postları (/tt/user/posts)
  Instagram — hesab postları (/instagram/user/posts) və rəsmi postların altındakı şərhlər (/instagram/post/comments).
              Instagram API-də açar sözlə post axtarışı yoxdur, ona görə izlənən hesablar konfiqurasiya edilir.

Toplanan hər element `RawNews`-a çevrilir və adi pipeline-dan keçir:
DGK relevance → (kateqoriya ‖ sentiment) → risk → insan yoxlaması. Burada heç bir analiz edilmir.

Təhlükəsizlik: EnsembleData tokeni yalnız URL parametri kimi qəbul edir. Token heç vaxt loga, xəta
mesajına və ya API cavabına yazılmır (`_redact`).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import NewsItem, Setting
from app.pipeline.process import RawNews

log = logging.getLogger(__name__)

# Sorğu başına unit qiyməti (EnsembleData sənədlərindən). Instagram postları: qaytarılan post sayı qədər.
COST = {"/tt/keyword/search": 1, "/tt/hashtag/posts": 1, "/instagram/user/info": 3, "/instagram/post/comments": 2,
        "/instagram/search": 4, "/customer/get-used-units": 0}

TOKEN_KEY = "ensembledata.token"
CONFIG_KEY = "ensembledata.config"
IGID_KEY = "ensembledata.instagram_ids"


class EnsembleDataError(RuntimeError):
    pass


class AuthError(EnsembleDataError):
    """491/492/493 — token tapılmadı, e-poçt təsdiqlənməyib, abunə bitib."""


class QuotaError(EnsembleDataError):
    """495 — günlük unit limiti bitib."""


class BudgetExceeded(EnsembleDataError):
    """Bu toplama üçün təyin edilmiş unit büdcəsi bitdi."""


# ------------------------------------------------------------------ token / konfiqurasiya
def get_token() -> str:
    try:
        with session_scope() as db:
            s = db.get(Setting, TOKEN_KEY)
            if s and s.value.get("token"):
                return str(s.value["token"])
    except Exception:  # baza hələ hazır deyilsə mühit dəyişəninə keç
        pass
    return get_settings().ensembledata_token


def mask(token: str) -> str | None:
    return f"…{token[-4:]}" if token else None


def effective_config(db=None) -> dict[str, Any]:
    """Mühit dəyişənlərindən gələn default + admin paneldə saxlanılan dəyişikliklər.
    `db` verilsə, həmin sessiyadan oxuyur (hələ commit olunmamış dəyişiklik görünsün)."""
    s = get_settings()
    cfg = {
        "tiktok_keywords": s.ed_tiktok_keywords, "tiktok_hashtags": s.ed_tiktok_hashtags,
        "tiktok_period_days": s.ed_tiktok_period_days, "tiktok_country": s.ed_tiktok_country,
        "tiktok_official_accounts": s.ed_tiktok_official_accounts, "tiktok_media_accounts": s.ed_tiktok_media_accounts,
        "instagram_official_accounts": s.ed_instagram_official_accounts,
        "instagram_media_accounts": s.ed_instagram_media_accounts,
        "instagram_posts_per_account": s.ed_instagram_posts_per_account,
        "instagram_comment_posts": s.ed_instagram_comment_posts,
        "max_units_per_run": s.ensembledata_max_units_per_run,
    }
    def _apply(sess) -> None:
        row = sess.get(Setting, CONFIG_KEY)
        if row:
            cfg.update({k: v for k, v in row.value.items() if k in cfg})
    try:
        if db is not None:
            _apply(db)
        else:
            with session_scope() as sess:
                _apply(sess)
    except Exception:
        pass
    return cfg


# ------------------------------------------------------------------ HTTP müştəri
@dataclass
class EnsembleDataClient:
    token: str
    base_url: str = field(default_factory=lambda: get_settings().ensembledata_base_url)
    max_units: int = 150
    transport: httpx.BaseTransport | None = None  # testlərdə MockTransport
    units_spent: int = 0
    calls: int = 0
    log_entries: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._http = httpx.Client(base_url=self.base_url, timeout=get_settings().ensembledata_timeout_s,
                                  transport=self.transport)

    def _redact(self, text: str) -> str:
        return text.replace(self.token, "***") if self.token else text

    def get(self, path: str, params: dict[str, Any], cost: int | None = None) -> dict[str, Any]:
        est = COST.get(path, 1) if cost is None else cost
        if self.units_spent + est > self.max_units:
            raise BudgetExceeded(f"unit büdcəsi bitdi ({self.units_spent}/{self.max_units}); {path} çağırılmadı")
        q = {k: v for k, v in params.items() if v is not None and v != ""}
        last_exc: Exception | None = None
        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                r = self._http.get(path, params={**q, "token": self.token})
            except httpx.HTTPError as exc:
                last_exc = EnsembleDataError(self._redact(f"{type(exc).__name__}: {exc}"))
                time.sleep(0.5 * (attempt + 1))
                continue
            ms = round((time.perf_counter() - t0) * 1000, 1)
            self.calls += 1
            self.log_entries.append({"path": path, "params": q, "status": r.status_code, "ms": ms})
            if r.status_code == 200:
                self.units_spent += est
                return r.json()
            detail = self._redact(r.text[:300])
            if r.status_code in (491, 492, 493):
                raise AuthError(f"EnsembleData token xətası ({r.status_code}): {detail}")
            if r.status_code == 422 and '"token"' in r.text:
                raise AuthError("Token formatı yanlışdır (EnsembleData tokeni 16 simvoldan ibarətdir)")
            if r.status_code == 495:
                raise QuotaError("EnsembleData günlük unit limiti bitib")
            if r.status_code >= 500:
                last_exc = EnsembleDataError(f"{path}: {r.status_code} {detail}")
                time.sleep(0.5 * (attempt + 1))
                continue
            raise EnsembleDataError(f"{path}: {r.status_code} {detail}")
        raise last_exc or EnsembleDataError(f"{path}: naməlum xəta")

    def used_units_today(self) -> dict[str, Any]:
        return self.get("/customer/get-used-units", {"date": datetime.now(timezone.utc).date().isoformat()}).get("data", {})


# ------------------------------------------------------------------ parse
def _ts(v: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _title(text: str, n: int = 140) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def parse_tiktok(aweme: dict[str, Any], kind: str = "social") -> RawNews | None:
    a = aweme.get("aweme_info", aweme)
    desc = (a.get("desc") or "").strip()
    aid = str(a.get("aweme_id") or "")
    if not aid or len(desc) < 10:
        return None
    au = a.get("author") or {}
    handle = au.get("unique_id") or au.get("nickname") or "naməlum"
    st = a.get("statistics") or {}
    return RawNews(
        source_name=f"TikTok @{handle}" if kind != "social" else "TikTok",
        source_kind=kind, title=_title(desc), body=desc, published_at=_ts(a.get("create_time")),
        url=f"https://www.tiktok.com/@{handle}/video/{aid}", platform="tiktok", external_id=aid, author_handle=handle,
        engagement={"views": int(st.get("play_count") or 0), "likes": int(st.get("digg_count") or 0),
                    "comments": int(st.get("comment_count") or 0), "shares": int(st.get("share_count") or 0)},
    )


def parse_instagram_post(node: dict[str, Any], kind: str, handle: str) -> RawNews | None:
    edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
    caption = (edges[0]["node"].get("text") if edges else "") or ""
    pid = str(node.get("id") or "")
    if not pid or len(caption.strip()) < 10:
        return None
    sc = node.get("shortcode")
    return RawNews(
        source_name=f"Instagram @{handle}", source_kind=kind, title=_title(caption), body=caption.strip(),
        published_at=_ts(node.get("taken_at_timestamp")), url=f"https://www.instagram.com/p/{sc}/" if sc else None,
        platform="instagram", external_id=pid, author_handle=handle,
        engagement={"likes": int((node.get("edge_media_preview_like") or {}).get("count") or 0),
                    "comments": int((node.get("edge_media_to_comment") or {}).get("count") or 0),
                    "views": int(node.get("video_view_count") or node.get("video_play_count") or 0)},
    )


def parse_instagram_comment(c: dict[str, Any], post: RawNews) -> RawNews | None:
    n = c.get("node", c)
    text = (n.get("text") or "").strip()
    cid = str(n.get("pk") or n.get("id") or "")
    # Yalnız emoji və ya istifadəçi qeydindən ibarət şərhlər analiz üçün yararsızdır
    letters = sum(ch.isalpha() for ch in text)
    if not cid or letters < 8:
        return None
    handle = (n.get("user") or {}).get("username") or "naməlum"
    return RawNews(
        # Başlıq kontekst verir: şərh DGK-nın rəsmi postunun altındadır (relevance bunu nəzərə alır)
        source_name="Instagram şərhləri", source_kind="social",
        title=f"Dövlət Gömrük Komitəsinin rəsmi Instagram postuna şərh",
        body=text, published_at=_ts(n.get("created_at")), url=post.url, platform="instagram",
        external_id=f"c{cid}", author_handle=handle,
        engagement={"likes": int(n.get("comment_like_count") or 0), "replies": int(n.get("child_comment_count") or 0),
                    "parent_post": post.external_id},
    )


# ------------------------------------------------------------------ toplayıcı
class SocialCollector:
    name = "ensembledata"

    def __init__(self, client: EnsembleDataClient | None = None, config: dict[str, Any] | None = None):
        self.cfg = config or effective_config()
        self.client = client or EnsembleDataClient(token=get_token(), max_units=int(self.cfg["max_units_per_run"]))
        self.errors: list[str] = []
        self.stats: dict[str, int] = {}

    def _known(self, platform: str, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        with session_scope() as db:
            return set(db.scalars(select(NewsItem.external_id).where(NewsItem.platform == platform,
                                                                      NewsItem.external_id.in_(ids))))

    def _ig_user_id(self, username: str) -> int | None:
        with session_scope() as db:
            row = db.get(Setting, IGID_KEY)
            cache = dict(row.value) if row else {}
        if username in cache:
            return int(cache[username])
        data = self.client.get("/instagram/user/info", {"username": username}).get("data") or {}
        pk = data.get("pk") or data.get("pk_id") or data.get("id")
        if not pk:
            return None
        cache[username] = int(pk)
        with session_scope() as db:
            row = db.get(Setting, IGID_KEY)
            if row:
                row.value = cache
            else:
                db.add(Setting(key=IGID_KEY, value=cache))
        return int(pk)

    def _step(self, label: str, fn) -> list[RawNews]:
        try:
            out = fn()
            self.stats[label] = len(out)
            return out
        except (AuthError, QuotaError):
            raise
        except BudgetExceeded as exc:
            self.errors.append(str(exc))
            raise
        except Exception as exc:
            self.errors.append(f"{label}: {exc}")
            log.warning("ensembledata %s: %s", label, exc)
            return []

    def fetch(self) -> list[RawNews]:
        if not self.client.token:
            raise AuthError("EnsembleData tokeni konfiqurasiya edilməyib")
        c = self.cfg
        items: list[RawNews] = []
        official_tt = {a.lower().lstrip("@") for a in c["tiktok_official_accounts"]}
        media_tt = {a.lower().lstrip("@") for a in c["tiktok_media_accounts"]}

        def tt_kind(r: RawNews) -> RawNews:
            h = (r.author_handle or "").lower()
            if h in official_tt or h in media_tt:
                r.source_kind = "official" if h in official_tt else "media"
                r.source_name = f"TikTok @{r.author_handle}"
            return r

        try:
            for kw in c["tiktok_keywords"]:
                items += self._step(f"tt_keyword:{kw}", lambda kw=kw: [tt_kind(r) for r in (
                    parse_tiktok(a) for a in (self.client.get("/tt/keyword/search", {
                        "name": kw, "period": c["tiktok_period_days"], "sorting": 2,
                        "country": c["tiktok_country"]}).get("data") or {}).get("data", [])) if r])
            for tag in c["tiktok_hashtags"]:
                items += self._step(f"tt_hashtag:{tag}", lambda tag=tag: [tt_kind(r) for r in (
                    parse_tiktok(a) for a in (self.client.get("/tt/hashtag/posts", {"name": tag.lstrip("#")})
                                               .get("data") or {}).get("data", [])) if r])
            for acc in list(official_tt) + list(media_tt):
                items += self._step(f"tt_user:{acc}", lambda acc=acc: [tt_kind(r) for r in (
                    parse_tiktok(a) for a in (self.client.get("/tt/user/posts", {"username": acc, "depth": 1}, cost=2)
                                               .get("data") or [])) if r])
            n_posts = int(c["instagram_posts_per_account"])
            for acc, kind in [(a, "official") for a in c["instagram_official_accounts"]] + \
                             [(a, "media") for a in c["instagram_media_accounts"]]:
                acc = acc.lstrip("@")

                def ig(acc=acc, kind=kind) -> list[RawNews]:
                    uid = self._ig_user_id(acc)
                    if not uid:
                        raise EnsembleDataError(f"Instagram hesabı tapılmadı: {acc}")
                    data = self.client.get("/instagram/user/posts", {"user_id": uid, "depth": 1, "chunk_size": n_posts},
                                           cost=n_posts).get("data") or {}
                    posts = [p for p in (parse_instagram_post(x.get("node", x), kind, acc) for x in data.get("posts", [])) if p]
                    out = list(posts)
                    if kind == "official":
                        for p in posts[: int(c["instagram_comment_posts"])]:
                            cm = self.client.get("/instagram/post/comments", {"media_id": int(p.external_id),
                                                                              "sorting": "recent", "cursor": ""})
                            out += [x for x in (parse_instagram_comment(cc, p) for cc in
                                                (cm.get("data") or {}).get("comments", [])) if x]
                    return out
                items += self._step(f"ig:{acc}", ig)
        except BudgetExceeded:
            pass  # toplanan qədəri emal olunur

        # Eyni element bir neçə axtarışda gələ bilər; artıq bazada olanlar yenidən emal olunmur
        uniq: dict[tuple[str, str], RawNews] = {}
        for r in items:
            uniq.setdefault((r.platform or "", r.external_id or ""), r)
        known = {p: self._known(p, [k[1] for k in uniq if k[0] == p]) for p in ("tiktok", "instagram")}
        fresh = [r for (p, eid), r in uniq.items() if eid not in known.get(p, set())]
        self.stats.update({"fetched_total": len(items), "unique": len(uniq), "new": len(fresh),
                           "units_spent": self.client.units_spent, "api_calls": self.client.calls})
        return fresh
