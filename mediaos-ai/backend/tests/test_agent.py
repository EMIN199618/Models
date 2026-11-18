"""4. Tool-calling — AI Analyst agent: alət seçimi, sxem, icazə, timeout, audit, insan təsdiqi."""
import time
import uuid

import pytest
from sqlalchemy import func, select

from app.agent import tools as T
from app.config import get_settings
from app.db import session_scope
from app.models import ToolCallLog
from tests.conftest import auth

EXAMPLES = [
    ("Bu gün DGK haqqında hansı xəbərlər yayımlanıb?", {"search_news"}),
    ("Son 7 gündə mənfi rəylər hansı mövzularla bağlıdır?", {"get_trends", "search_news"}),
    ("Astara gömrüyü haqqında şikayətləri göstər.", {"search_news"}),
    ("Qırmızı Körpüdə əməkdaşın pul tələb etməsi əvvəl də yayımlanıb?", {"semantic_search"}),
    ("Qırmızı Körpüdə rüşvət tələb olunması iddiası rəsmi mənbədə təsdiqlənib?", {"search_official_sources"}),
    ("Son bir ayda gömrük fəaliyyətinə dair əsas ictimai narazılıqlar hansılardır?", {"get_trends", "search_news"}),
    ("DGK rəhbərliyi üçün gündəlik analitik icmal hazırla.", {"generate_report"}),
]


@pytest.mark.parametrize("question,expected_tools", EXAMPLES)
def test_example_questions(client, question, expected_tools):
    r = client.post("/api/chat", headers=auth("analyst"), json={"question": question})
    assert r.status_code == 200, r.text
    b = r.json()
    used = {t["tool"] for t in b["tools"]}
    assert expected_tools <= used
    assert all(t["status"] == "ok" for t in b["tools"])
    assert "Vaxt aralığı" in b["answer"] or "Təsdiq statusu" in b["answer"]
    assert b["validation"]["removed_citations"] == []


def test_fact_check_detects_official_denial(client):
    r = client.post("/api/chat", headers=auth("viewer"),
                    json={"question": "Qırmızı Körpü gömrük postunda rüşvət tələb olunması iddiası rəsmi mənbədə təsdiqlənib?"})
    b = r.json()
    assert "TƏKZİB" in b["answer"]
    assert any(c["ref"].startswith("S") for c in b["citations"])


def test_negative_topics_question_returns_cited_items(client):
    b = client.post("/api/chat", headers=auth("analyst"),
                    json={"question": "Son 7 gündə mənfi rəylər hansı mövzularla bağlıdır?"}).json()
    assert b["citations"] and all(c["ref"].startswith("N") for c in b["citations"])
    assert "Statistika" in b["answer"]


def _ctx(role="viewer"):
    return T.ToolContext(user_id=1, role=role, conversation_id=uuid.uuid4())


def test_permission_denied_for_viewer():
    out = T.execute_tool(_ctx("viewer"), "generate_report", {})
    assert out["status"] == "denied"


def test_schema_validation_rejects_bad_args():
    out = T.execute_tool(_ctx("analyst"), "search_news", {"limit": 999})
    assert out["status"] == "invalid"
    out = T.execute_tool(_ctx("analyst"), "drop_database", {})
    assert out["status"] == "invalid"


def test_tool_timeout(monkeypatch):
    def slow(ctx, a):
        time.sleep(1.5)
        return {"items": []}
    spec = T.TOOLS["get_trends"]
    monkeypatch.setitem(T.TOOLS, "get_trends", T.ToolSpec(spec.name, spec.description, spec.schema, slow, spec.roles))
    monkeypatch.setattr(get_settings(), "tool_timeout_s", 0.3)
    out = T.execute_tool(_ctx("analyst"), "get_trends", {})
    assert out["status"] == "timeout"


def test_tool_calls_are_audited():
    with session_scope() as db:
        before = db.scalar(select(func.count()).select_from(ToolCallLog))
    T.execute_tool(_ctx("viewer"), "get_trends", {"group_by": "category"})
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(ToolCallLog)) == before + 1


def test_agent_has_no_write_tools():
    forbidden = ("delete", "update", "drop", "insert", "publish", "send", "email", "http")
    assert not [n for n in T.TOOLS if any(f in n for f in forbidden)]


def test_report_requires_human_approval(client):
    b = client.post("/api/chat", headers=auth("analyst"), json={"question": "Son 7 gün üçün analitik icmal hazırla"}).json()
    rid = next(c for c in b["tools"] if c["tool"] == "generate_report")
    reports = client.get("/api/reports", headers=auth("analyst")).json()
    rep = reports[0]
    assert rep["status"] == "pending_approval"
    review = [r for r in client.get("/api/review?kind=report", headers=auth("analyst")).json() if r["report_id"] == rep["id"]][0]
    assert client.post(f"/api/review/{review['id']}/decide", headers=auth("analyst"), json={"approve": True}).status_code == 403
    assert client.post(f"/api/review/{review['id']}/decide", headers=auth("admin"), json={"approve": True}).status_code == 200
    assert client.get(f"/api/reports/{rep['id']}", headers=auth("viewer")).json()["status"] == "published"
    assert rid


def test_high_risk_signal_requires_confirmation(client):
    items = client.get("/api/review?kind=risk", headers=auth("analyst")).json()
    assert items, "yüksək/orta risk siqnalları insan yoxlamasına düşməlidir"
    target = items[0]
    assert client.post(f"/api/review/{target['id']}/decide", headers=auth("viewer"), json={"approve": True}).status_code == 403
    assert client.post(f"/api/review/{target['id']}/decide", headers=auth("analyst"), json={"approve": True, "note": "təsdiq"}).status_code == 200
    nid = target["news"]["id"]
    assert client.get(f"/api/news/{nid}", headers=auth("viewer")).json()["analysis"]["risk_status"] == "confirmed"


def test_ai_answer_cache_is_per_user(client):
    q = {"question": "Son bir ayda Biləsuvar gömrük postu haqqında hansı xəbərlər var?"}
    a1 = client.post("/api/chat", headers=auth("analyst"), json=q).json()
    a2 = client.post("/api/chat", headers=auth("analyst"), json=q).json()
    b1 = client.post("/api/chat", headers=auth("analyst2"), json=q).json()
    assert a1["cached"] is False and a2["cached"] is True
    assert b1["cached"] is False  # başqa istifadəçi eyni keşdən istifadə etmir
