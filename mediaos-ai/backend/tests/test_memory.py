"""3. Memory — qısamüddətli kontekst, uzunmüddətli təsdiqli yaddaş, izolyasiya, silinmə, saxlanma."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import session_scope
from app.memory import service as mem
from app.models import AuditLog, MemoryItem, User
from tests.conftest import auth


def test_follow_up_question_uses_short_term_context(client):
    r1 = client.post("/api/chat", headers=auth("analyst"), json={"question": "Astara gömrüyü haqqında şikayətləri göstər."})
    assert r1.status_code == 200, r1.text
    cid = r1.json()["conversation_id"]
    r2 = client.post("/api/chat", headers=auth("analyst"),
                     json={"question": "Bunlardan hansıları son 7 gündə yayımlanıb?", "conversation_id": cid})
    body = r2.json()
    assert body["uses"]["memory"]["short_term_messages"] == 2
    # Davam sualında yer (Astara) əvvəlki sualdan götürülüb
    assert any(t["args"].get("location") == "Astara" for t in body["tools"])


def test_other_user_cannot_read_or_continue_conversation(client):
    cid = client.post("/api/chat", headers=auth("analyst"), json={"question": "Bu gün DGK haqqında hansı xəbərlər yayımlanıb?"}).json()["conversation_id"]
    assert client.get(f"/api/conversations/{cid}/messages", headers=auth("analyst2")).status_code == 404
    assert client.post("/api/chat", headers=auth("analyst2"), json={"question": "davam et", "conversation_id": cid}).status_code == 404
    assert client.get(f"/api/conversations/{cid}/messages", headers=auth("analyst")).status_code == 200


def test_long_term_memory_requires_approval_and_rejects_pii(client):
    h = auth("analyst")
    bad = client.post("/api/memory", headers=h, json={"kind": "note", "key": "əlaqə", "value": {"tel": "+994 50 123 45 67"}})
    assert bad.status_code == 422
    bad_kind = client.post("/api/memory", headers=h, json={"kind": "password", "key": "x", "value": {}})
    assert bad_kind.status_code == 422
    r = client.post("/api/memory", headers=h, json={"kind": "monitoring_topic", "key": "əsas_mövzu", "value": {"topic": "Astara növbələri"}})
    mid = r.json()["id"]
    with session_scope() as db:
        uid = db.scalar(select(User.id).where(User.username == "analyst"))
        assert "Astara növbələri" not in mem.memory_context(db, uid)  # təsdiqsiz istifadə olunmur
    assert client.post(f"/api/memory/{mid}/approve", headers=h).status_code == 200
    with session_scope() as db:
        assert "Astara növbələri" in mem.memory_context(db, uid)
    # Başqa istifadəçi görə, təsdiqləyə və silə bilməz
    assert all(m["id"] != mid for m in client.get("/api/memory", headers=auth("analyst2")).json())
    assert client.delete(f"/api/memory/{mid}", headers=auth("analyst2")).status_code == 404
    assert client.delete(f"/api/memory/{mid}", headers=h).status_code == 204
    with session_scope() as db:
        assert "Astara növbələri" not in mem.memory_context(db, uid)
        actions = set(db.scalars(select(AuditLog.action).where(AuditLog.target == f"memory:{mid}")))
    assert {"memory.propose", "memory.approve", "memory.delete"} <= actions


def test_retention_purge_expires_old_items():
    with session_scope() as db:
        uid = db.scalar(select(User.id).where(User.username == "analyst2"))
        it = mem.propose_memory(db, uid, "note", "köhnə", {"x": 1})
        it.approved = True
        it.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        iid = it.id
    with session_scope() as db:
        st = mem.purge_expired(db)
    assert st["memory_expired"] >= 1
    with session_scope() as db:
        assert db.get(MemoryItem, iid).deleted_at is not None


def test_memory_layers_are_separate():
    """Şəxsi yaddaş RAG indeksinə düşmür."""
    from app.rag.retriever import PgVectorRetriever
    docs = PgVectorRetriever(role="admin", k=20).invoke("Astara növbələri əsas_mövzu monitoring_topic")
    assert all(d.metadata["doc_type"] != "memory" for d in docs)
    assert all("əsas_mövzu" not in d.page_content for d in docs)
