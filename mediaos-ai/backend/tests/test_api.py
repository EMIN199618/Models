"""API: autentifikasiya, rollar, rate limit, sağlamlıq, metriklər, kritik qaydalar."""
from app.config import get_settings
from tests.conftest import auth


def test_health(client):
    b = client.get("/health").json()
    assert b["postgres"] is True and b["redis"] is True and b["llm"]["provider"] == "local"


def test_auth_required_and_roles(client):
    assert client.get("/api/dashboard/stats").status_code == 401
    assert client.get("/api/dashboard/stats", headers={"Authorization": "Bearer yanlis"}).status_code == 401
    assert client.post("/api/ingest/news", headers=auth("viewer"), json=[]).status_code == 403
    assert client.get("/api/review", headers=auth("viewer")).status_code == 403
    assert client.get("/api/metrics", headers=auth("viewer")).status_code == 403


def test_rate_limit_returns_429(client, monkeypatch):
    from app.cache.redis_cache import get_cache
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3)
    get_cache()._client.delete(*get_cache()._client.keys("mos:rl:api:*") or ["_"])
    codes = [client.get("/api/news/latest?limit=1", headers=auth("viewer")).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]


def test_irrelevant_news_never_in_feed(client):
    titles = [n["title"] for n in client.get("/api/news/latest?limit=100", headers=auth("admin")).json()]
    for bad in ("Gürcüstan gömrüyündə", "Rusiya Federal Gömrük", "Futbol", "Hava proqnozu", "Neft qiymətləri", "Avrasiya"):
        assert not any(bad in t for t in titles), bad


def test_content_types_are_separated(client):
    for ct in ("official", "media", "public_opinion"):
        items = client.get(f"/api/news/latest?limit=100&content_type={ct}", headers=auth("viewer")).json()
        assert items and all(i["content_type"] == ct for i in items)


def test_duplicate_not_in_feed(client):
    titles = [n["title"] for n in client.get("/api/news/latest?limit=100", headers=auth("viewer")).json()]
    assert titles.count("Astara gömrük postunda 12 kq narkotik vasitənin qaçaqmalçılığının qarşısı alınıb") == 1


def test_news_detail_shows_prompt_versions(client):
    nid = client.get("/api/news/latest?limit=1", headers=auth("viewer")).json()[0]["id"]
    a = client.get(f"/api/news/{nid}", headers=auth("viewer")).json()["analysis"]
    assert set(a["prompt_versions"]) == {"relevance", "category", "sentiment", "risk"}


def test_metrics_endpoint(client):
    client.get("/api/dashboard/stats", headers=auth("analyst"))
    m = client.get("/api/metrics", headers=auth("analyst")).json()
    assert {"cache", "api_latency", "llm", "tools", "review_queue", "collectors"} <= set(m)
    assert m["llm"]["relevance"]["calls"] > 0 and m["llm"]["relevance"]["input_tokens"] > 0
    route = m["api_latency"]["/api/dashboard/stats"]
    assert route["p50_ms"] is not None and route["p95_ms"] >= route["p50_ms"]


def test_prompts_listing(client):
    names = {p["name"] for p in client.get("/api/prompts", headers=auth("viewer")).json()}
    assert {"dgk_relevance", "news_category", "sentiment", "risk_assessment", "fact_check", "rag_qa", "executive_summary"} <= names
