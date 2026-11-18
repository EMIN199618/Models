"""Üçsəviyyəli yaddaş.

1) Short-term  — cari söhbətin son N mesajı. Redis-də (sürət) + `chat_messages`-də (davamlı).
                 Açar istifadəçi + söhbət id-si ilə qurulur; söhbətin sahibi DB-də yoxlanılır.
2) Long-term   — `memory_items`: yalnız icazəli növlər, yalnız istifadəçinin təsdiqlədiyi qeydlər,
                 saxlanma müddəti, yumşaq silinmə, audit.
3) Institutional — DGK sənədləri və tarixi xəbərlər; RAG (documents/chunks) vasitəsilə, ayrıca qat.

Qatlar heç vaxt qarışmır: şəxsi yaddaş RAG indeksinə yazılmır, RAG sənədi şəxsi yaddaşa düşmür.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.cache.redis_cache import PREFIX, get_cache
from app.config import get_settings
from app.models import AuditLog, ChatMessage, Conversation, MemoryItem

ALLOWED_KINDS = {"dashboard_pref", "monitoring_topic", "query_template", "note"}
PII = re.compile(
    r"(\+?994[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}|[\w.+-]+@[\w-]+\.[\w.]+|\b[A-Z0-9]{7}\b|\bAZE\d{8}\b)"
)


class MemoryError_(ValueError):
    pass


# ----------------------------------------------------------------- short-term
def get_or_create_conversation(db: Session, user_id: int, conversation_id: str | None) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, uuid.UUID(conversation_id))
        if conv is None or conv.user_id != user_id:
            # Başqa istifadəçinin söhbətinə giriş qadağandır — mövcudluğu da açıqlanmır
            raise PermissionError("söhbət tapılmadı")
        return conv
    conv = Conversation(user_id=user_id)
    db.add(conv)
    db.flush()
    return conv


def _stm_key(user_id: int, conv_id: uuid.UUID) -> str:
    return f"{PREFIX}:stm:u{user_id}:{conv_id}"


def load_history(db: Session, user_id: int, conv: Conversation) -> list[BaseMessage]:
    s = get_settings()
    cache = get_cache()
    key = _stm_key(user_id, conv.id)
    raw = cache._call(lambda: cache._client.lrange(key, -s.short_term_max_messages, -1), None)
    if raw:
        return messages_from_dict([json.loads(r) for r in raw])
    rows = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv.id, ChatMessage.user_id == user_id)
                      .order_by(ChatMessage.id.desc()).limit(s.short_term_max_messages)).all()[::-1]
    from langchain_core.messages import AIMessage, HumanMessage
    msgs: list[BaseMessage] = [HumanMessage(r.content) if r.role == "human" else AIMessage(r.content) for r in rows
                               if r.role in ("human", "ai")]
    if msgs:
        _push(user_id, conv.id, msgs)
    return msgs


def _push(user_id: int, conv_id: uuid.UUID, msgs: list[BaseMessage]) -> None:
    s = get_settings()
    cache = get_cache()
    key = _stm_key(user_id, conv_id)

    def _do():
        p = cache._client.pipeline()
        for d in messages_to_dict(msgs):
            p.rpush(key, json.dumps(d, ensure_ascii=False))
        p.ltrim(key, -s.short_term_max_messages, -1)
        p.expire(key, s.short_term_ttl_s)
        p.execute()
    cache._call(_do, None)


def append_turn(db: Session, user_id: int, conv: Conversation, human: str, ai: str, meta: dict[str, Any]) -> None:
    from langchain_core.messages import AIMessage, HumanMessage
    db.add(ChatMessage(conversation_id=conv.id, user_id=user_id, role="human", content=human))
    db.add(ChatMessage(conversation_id=conv.id, user_id=user_id, role="ai", content=ai, meta=meta))
    if not conv.title:
        conv.title = human[:120]
    _push(user_id, conv.id, [HumanMessage(human), AIMessage(ai)])


# ----------------------------------------------------------------- long-term
def propose_memory(db: Session, user_id: int, kind: str, key: str, value: dict[str, Any], ttl_days: int | None = None) -> MemoryItem:
    if kind not in ALLOWED_KINDS:
        raise MemoryError_(f"icazəsiz yaddaş növü: {kind}")
    if PII.search(json.dumps(value, ensure_ascii=False)) or PII.search(key):
        raise MemoryError_("şəxsi məlumat (telefon, e-poçt, FİN, pasport) yaddaşda saxlanıla bilməz")
    days = ttl_days or get_settings().long_term_retention_days
    item = MemoryItem(user_id=user_id, kind=kind, key=key[:128], value=value, approved=False,
                      expires_at=datetime.now(timezone.utc) + timedelta(days=days))
    db.add(item)
    db.flush()
    db.add(AuditLog(user_id=user_id, action="memory.propose", target=f"memory:{item.id}", detail={"kind": kind, "key": key}))
    return item


def approve_memory(db: Session, user_id: int, item_id: int) -> MemoryItem:
    item = db.get(MemoryItem, item_id)
    if not item or item.user_id != user_id or item.deleted_at:
        raise PermissionError("yaddaş elementi tapılmadı")
    item.approved = True
    db.add(AuditLog(user_id=user_id, action="memory.approve", target=f"memory:{item.id}"))
    get_cache().delete_scope("ai_answer", f"user:{user_id}")
    return item


def delete_memory(db: Session, user_id: int, item_id: int) -> None:
    item = db.get(MemoryItem, item_id)
    if not item or item.user_id != user_id or item.deleted_at:
        raise PermissionError("yaddaş elementi tapılmadı")
    item.deleted_at = datetime.now(timezone.utc)
    item.value = {"_deleted": True}
    db.add(AuditLog(user_id=user_id, action="memory.delete", target=f"memory:{item.id}"))
    get_cache().delete_scope("ai_answer", f"user:{user_id}")


def list_memory(db: Session, user_id: int, approved_only: bool = False) -> list[MemoryItem]:
    now = datetime.now(timezone.utc)
    q = select(MemoryItem).where(MemoryItem.user_id == user_id, MemoryItem.deleted_at.is_(None),
                                 (MemoryItem.expires_at.is_(None)) | (MemoryItem.expires_at > now))
    if approved_only:
        q = q.where(MemoryItem.approved.is_(True))
    return list(db.scalars(q.order_by(MemoryItem.id)))


def memory_context(db: Session, user_id: int) -> str:
    items = list_memory(db, user_id, approved_only=True)
    if not items:
        return "(yoxdur)"
    return "; ".join(f"{i.kind}:{i.key}={json.dumps(i.value, ensure_ascii=False)}" for i in items[:20])


def purge_expired(db: Session) -> dict[str, int]:
    """Saxlanma müddəti bitmiş yaddaşı və köhnə söhbətləri silir (worker gündəlik işlədir)."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    r1 = db.execute(update(MemoryItem).where(MemoryItem.expires_at < now, MemoryItem.deleted_at.is_(None))
                    .values(deleted_at=now, value={"_expired": True}))
    r2 = db.execute(delete(ChatMessage).where(ChatMessage.created_at < now - timedelta(days=s.chat_history_retention_days)))
    stats = {"memory_expired": r1.rowcount or 0, "chat_messages_deleted": r2.rowcount or 0}
    db.add(AuditLog(action="memory.purge", detail=stats))
    return stats
