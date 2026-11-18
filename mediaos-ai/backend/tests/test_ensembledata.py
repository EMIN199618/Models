"""EnsembleData (TikTok + Instagram) inteqrasiyası.

HTTP cavablar EnsembleData OpenAPI nümunələrinin strukturu ilə qurulub (aweme_info / statistics / author;
Instagram node / edge_media_to_caption / comments). Məzmun sintetikdir.
"""
import json
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select

from app.collectors import ensembledata as ED
from app.collectors.collectors import run_collector
from app.db import session_scope
from app.models import AuditLog, NewsItem
from tests.conftest import auth

TOKEN = "test_token_1234567890abcdef"
NOW = int(datetime.now(timezone.utc).timestamp())


def aweme(aid, desc, handle="istifadeci1", views=1000, shares=3, wrap=True):
    a = {"aweme_id": aid, "desc": desc, "create_time": NOW - 3600, "author": {"unique_id": handle, "nickname": handle},
         "statistics": {"play_count": views, "digg_count": views // 20, "comment_count": 12, "share_count": shares}}
    return {"type": 1, "aweme_info": a} if wrap else a


KEYWORD = {"data": {"nextCursor": 20, "data": [
    aweme("7400000000000000001", "Astara gömrüyündə sürücülərdən pul tələb edirlər, rüşvətsiz keçmək olmur! Hamı bunu bilir",
          views=120_000, shares=900),
    aweme("7400000000000000002", "Kapıkule gümrük kapısında bugün 3 saatlik bekleyiş var, tır şoförleri isyan etti"),
    aweme("7400000000000000003", "Qirmizi korpu gomrukunde 4 saat novbe gozledik, problem hell olunmur"),
    aweme("7400000000000000004", "🔥🔥"),
]}}
HASHTAG = {"data": {"nextCursor": 20, "data": [
    aweme("7400000000000000001", "Astara gömrüyündə sürücülərdən pul tələb edirlər, rüşvətsiz keçmək olmur! Hamı bunu bilir",
          views=120_000, shares=900, wrap=False),
    aweme("7400000000000000005", "Dövlət Gömrük Komitəsi e-gömrük xidmətlərinin yeni imkanlarını təqdim edir",
          handle="dgk_test_official", wrap=False),
]}}
IG_INFO = {"data": {"pk": 555001, "username": "dgk_test_ig"}}
IG_POSTS = {"data": {"count": 2, "last_cursor": "", "posts": [
    {"node": {"id": "3500000000000000001", "shortcode": "TESTabc1", "taken_at_timestamp": NOW - 7200,
              "edge_media_to_caption": {"edges": [{"node": {"text": "Dövlət Gömrük Komitəsi: Biləsuvar gömrük postunda yeni terminal istifadəyə verilib"}}]},
              "edge_media_preview_like": {"count": 340}, "edge_media_to_comment": {"count": 3}}},
    {"node": {"id": "3500000000000000002", "shortcode": "TESTabc2", "taken_at_timestamp": NOW - 9000,
              "edge_media_to_caption": {"edges": [{"node": {"text": "DGK: Hava limanında bəyan edilməmiş valyuta aşkarlanıb"}}]},
              "edge_media_preview_like": {"count": 120}, "edge_media_to_comment": {"count": 1}}},
]}}
IG_COMMENTS = {"data": {"comments": [
    {"node": {"pk": "18000000000000001", "text": "Rüşvətxorluq bitməyincə heç nə dəyişməyəcək, Balakəndə yenə pul istədilər",
              "created_at": NOW - 600, "user": {"username": "vetendas_a"}, "child_comment_count": 4}},
    {"node": {"pk": "18000000000000002", "text": "🔥🔥👍", "created_at": NOW - 500, "user": {"username": "vetendas_b"}}},
    {"node": {"pk": "18000000000000003", "text": "Çox gözəl xidmətdir, təşəkkür edirəm, operativ işləyirlər",
              "created_at": NOW - 400, "user": {"username": "vetendas_c"}}},
]}}


def make_transport(calls, status_override=None):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.url.path, dict(req.url.params)))
        if status_override:
            return httpx.Response(status_override, json={"detail": f"error for token {req.url.params.get('token')}"})
        assert req.url.params.get("token") == TOKEN
        p = req.url.path.removeprefix("/apis")
        body = {"/tt/keyword/search": KEYWORD, "/tt/hashtag/posts": HASHTAG, "/instagram/user/info": IG_INFO,
                "/instagram/user/posts": IG_POSTS, "/instagram/post/comments": IG_COMMENTS,
                "/tt/user/posts": {"data": [], "nextCursor": 0},
                "/customer/get-used-units": {"data": {"tiktok": 12, "instagram": 30}}}.get(p)
        return httpx.Response(200, json=body) if body else httpx.Response(404, json={"detail": "not found"})
    return httpx.MockTransport(handler)


CFG = {"tiktok_keywords": ["gömrük"], "tiktok_hashtags": ["gomruk"], "tiktok_period_days": "7", "tiktok_country": "",
       "tiktok_official_accounts": ["dgk_test_official"], "tiktok_media_accounts": [],
       "instagram_official_accounts": ["dgk_test_ig"], "instagram_media_accounts": [],
       "instagram_posts_per_account": 2, "instagram_comment_posts": 1, "max_units_per_run": 100}


def collector(calls, max_units=100, status=None):
    client = ED.EnsembleDataClient(token=TOKEN, base_url="https://ensembledata.com/apis", max_units=max_units,
                                   transport=make_transport(calls, status))
    return ED.SocialCollector(client=client, config={**CFG, "max_units_per_run": max_units})


def test_parse_and_dedup_within_run():
    calls = []
    items = collector(calls).fetch()
    ids = [i.external_id for i in items]
    assert len(ids) == len(set(ids))
    assert "7400000000000000004" not in ids          # yalnız emoji — buraxılır
    assert "c18000000000000002" not in ids           # emoji şərh — buraxılır
    tt = next(i for i in items if i.external_id == "7400000000000000001")
    assert tt.platform == "tiktok" and tt.engagement["views"] == 120_000
    off = next(i for i in items if i.external_id == "7400000000000000005")
    assert off.source_kind == "official"            # konfiqurasiya edilmiş rəsmi hesab
    assert any(i.external_id.startswith("c") and i.platform == "instagram" for i in items)


def test_full_pipeline_relevance_risk_and_virality(client):
    calls = []
    res = run_collector(collector(calls))
    assert "error" not in res, res
    with session_scope() as db:
        rows = {n.external_id: n for n in db.scalars(select(NewsItem).where(NewsItem.platform.isnot(None)))}
        viral = rows["7400000000000000001"]
        assert viral.status == "relevant" and viral.content_type == "public_opinion"
        assert viral.analysis.risk_level == "high" and viral.analysis.risk_status == "pending_review"
        reasons = " ".join(viral.analysis.risk_reasons)
        assert "R1" in reasons and "R6" in reasons and "viral" in reasons
        assert rows["7400000000000000002"].status == "irrelevant"        # Türkiyə gömrüyü
        assert rows["7400000000000000003"].status == "relevant"          # ASCII yazılış tanınır
        assert rows["7400000000000000005"].content_type == "official"
        cm = rows["c18000000000000001"]
        assert cm.status == "relevant" and cm.content_type == "public_opinion" and cm.analysis.risk_level == "high"
        pos = rows["c18000000000000003"]
        assert pos.analysis.sentiment == "positive" and pos.analysis.risk_level == "low"
    # İkinci toplama eyni postları yenidən emal etmir
    res2 = run_collector(collector([]))
    assert res2["collector"]["new"] == 0


def test_feed_shows_platform_and_masks_private_handles(client):
    items = client.get("/api/news/latest?limit=100", headers=auth("viewer")).json()
    social = [i for i in items if i["platform"] in ("tiktok", "instagram")]
    assert social
    for i in social:
        if i["content_type"] == "public_opinion" and i["author"]:
            assert i["author"].endswith("***")
    stats = client.get("/api/dashboard/stats?days=7", headers=auth("viewer")).json()
    assert stats["by_platform"].get("tiktok", 0) >= 1 and stats["by_platform"].get("instagram", 0) >= 1


def test_budget_cap_stops_calls():
    calls = []
    c = collector(calls, max_units=2)
    c.fetch()
    assert c.client.units_spent <= 2
    assert any("büdcə" in e for e in c.errors)


@pytest.mark.parametrize("code,exc", [(491, ED.AuthError), (493, ED.AuthError), (495, ED.QuotaError)])
def test_api_errors_mapped_and_token_redacted(code, exc):
    c = collector([], status=code)
    with pytest.raises(exc) as ei:
        c.fetch()
    assert TOKEN not in str(ei.value)


def test_token_never_logged_or_returned(client, caplog):
    calls = []
    c = collector(calls)
    c.fetch()
    assert all("token" not in e["params"] for e in c.client.log_entries)
    assert TOKEN not in caplog.text
    with session_scope() as db:
        assert not any(TOKEN in json.dumps(a.detail, ensure_ascii=False) for a in db.scalars(select(AuditLog)))


def test_admin_endpoints(client, monkeypatch):
    # Token yoxlaması real şəbəkəyə getməsin
    monkeypatch.setattr(ED.EnsembleDataClient, "used_units_today", lambda self: {"tiktok": 0})
    assert client.put("/api/integrations/ensembledata/token", headers=auth("analyst"), json={"token": TOKEN}).status_code == 403
    r = client.put("/api/integrations/ensembledata/token", headers=auth("admin"), json={"token": TOKEN})
    assert r.status_code == 200 and r.json()["token"] == "…cdef"
    st = client.get("/api/integrations/ensembledata", headers=auth("admin")).json()
    assert st["configured"] and st["token"] == "…cdef" and TOKEN not in json.dumps(st)
    cfg = client.put("/api/integrations/ensembledata/config", headers=auth("admin"),
                     json={"instagram_official_accounts": ["dgk_test_ig"], "max_units_per_run": 80}).json()
    assert cfg["instagram_official_accounts"] == ["dgk_test_ig"] and cfg["max_units_per_run"] == 80
    assert client.put("/api/integrations/ensembledata/config", headers=auth("admin"),
                      json={"tiktok_period_days": "5"}).status_code == 422
    assert client.delete("/api/integrations/ensembledata/token", headers=auth("admin")).status_code == 204
    assert ED.get_token() == ""


def test_invalid_token_rejected(client, monkeypatch):
    def bad(self):
        raise ED.AuthError("EnsembleData token xətası (491): Token not found")
    monkeypatch.setattr(ED.EnsembleDataClient, "used_units_today", bad)
    r = client.put("/api/integrations/ensembledata/token", headers=auth("admin"), json={"token": "x" * 20})
    assert r.status_code == 400 and "491" in r.json()["detail"]


def test_malformed_token_gives_clear_message():
    def handler(req):
        return httpx.Response(422, json={"detail": [{"loc": ["query", "token"], "msg": "ensure this value has at most 16 characters"}]})
    c = ED.EnsembleDataClient(token="x" * 20, max_units=1, transport=httpx.MockTransport(handler))
    with pytest.raises(ED.AuthError, match="16 simvol"):
        c.used_units_today()
