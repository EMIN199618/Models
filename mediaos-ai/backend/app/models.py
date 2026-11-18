"""Verilənlər modeli.

Qatlar bir-birindən ayrıdır:
  * news_items / news_analysis        — monitorinq məlumatı
  * documents / chunks                — institusional bilik (RAG)
  * memory_items                      — istifadəçinin uzunmüddətli yaddaşı
  * conversations / chat_messages     — söhbət tarixçəsi (qısamüddətli yaddaşın davamlı nüsxəsi)
  * audit_logs / tool_calls / llm_calls / request_metrics — müşahidə və audit
"""
from datetime import datetime
from typing import Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base

EMB_DIM = get_settings().embedding_dim


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))  # viewer | analyst | admin
    api_token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    url: Mapped[str | None] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(32))  # official | media | social | complaint
    trust_level: Mapped[float] = mapped_column(Float, default=0.5)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)


class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    url: Mapped[str | None] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    simhash: Mapped[int] = mapped_column(BigInteger, index=True)
    # new | relevant | irrelevant | needs_review | duplicate
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    # official | media | public_opinion  — rəsmi xəbər, media materialı, ictimai rəy/şikayət ayrı saxlanılır
    content_type: Mapped[str] = mapped_column(String(16), index=True)
    dup_of_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id"))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    # Sosial şəbəkə sahələri (EnsembleData): platforma, xarici id, müəllif, qarşılıqlı əlaqə göstəriciləri
    platform: Mapped[str | None] = mapped_column(String(16), index=True)  # tiktok | instagram | web
    external_id: Mapped[str | None] = mapped_column(String(64), index=True)
    author_handle: Mapped[str | None] = mapped_column(String(128))
    engagement: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # [{"type": "image|video", "url", "thumb", "ocr_text", "transcript": [{"t": san, "text"}]}]
    media: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    language: Mapped[str | None] = mapped_column(String(8))

    source: Mapped[Source] = relationship()
    analysis: Mapped["NewsAnalysis | None"] = relationship(back_populates="news", uselist=False)


class NewsAnalysis(Base):
    __tablename__ = "news_analysis"
    news_id: Mapped[int] = mapped_column(ForeignKey("news_items.id", ondelete="CASCADE"), primary_key=True)
    is_relevant: Mapped[bool] = mapped_column(Boolean)
    relevance_score: Mapped[float] = mapped_column(Float)
    relevance_reason: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str | None] = mapped_column(String(32), index=True)
    sentiment: Mapped[str | None] = mapped_column(String(16), index=True)  # positive | neutral | negative
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str | None] = mapped_column(String(16), index=True)  # low | medium | high
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # auto | pending_review | confirmed | rejected — yüksək risk insan təsdiqi tələb edir
    risk_status: Mapped[str] = mapped_column(String(16), default="auto")
    location: Mapped[str | None] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # Relevance v2 sübutları
    relevance_level: Mapped[str | None] = mapped_column(String(16))  # DIRECT | CONTEXTUAL | WEAK | NONE
    matched_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    matched_entities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    evidence: Mapped[list[str]] = mapped_column(JSONB, default=list)
    prompt_versions: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    model: Mapped[str] = mapped_column(String(64), default="")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    news: Mapped[NewsItem] = relationship(back_populates="analysis")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(1024))
    # official_news | official_doc | legislation | media | monitoring | internal
    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    approval_status: Mapped[str] = mapped_column(String(16), default="approved")  # approved | pending | rejected
    access_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=lambda: ["viewer", "analyst", "admin"])
    news_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id", ondelete="SET NULL"))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    ord: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any] = mapped_column(Vector(EMB_DIM))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    document: Mapped[Document] = relationship()


class MemoryItem(Base):
    """Uzunmüddətli yaddaş: yalnız icazəli və təsdiqlənmiş məlumat."""
    __tablename__ = "memory_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # dashboard_pref | monitoring_topic | query_template | note
    kind: Mapped[str] = mapped_column(String(32))
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))  # human | ai | tool
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewItem(Base):
    """İnsan yoxlaması növbəsi: aşağı etibarlılıq, yüksək risk, hesabat dərci."""
    __tablename__ = "review_queue"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # relevance | risk | report | low_confidence
    news_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id", ondelete="CASCADE"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    period_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft | pending_approval | published | rejected
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str | None] = mapped_column(String(256))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ToolCallLog(Base):
    __tablename__ = "tool_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    tool: Mapped[str] = mapped_column(String(64), index=True)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), index=True)  # ok | error | denied | timeout | invalid
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LLMCallLog(Base):
    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    chain: Mapped[str] = mapped_column(String(64), index=True)
    prompt_name: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16))  # ok | error
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class RequestMetric(Base):
    __tablename__ = "request_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    route: Mapped[str] = mapped_column(String(128), index=True)
    method: Mapped[str] = mapped_column(String(8))
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    cache: Mapped[str | None] = mapped_column(String(8))  # hit | miss | bypass
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CollectorRun(Base):
    __tablename__ = "collector_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(256))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    irrelevant: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    # Ən yeni elementin dərc vaxtı ilə toplanma vaxtı arasındakı gecikmə (san.)
    max_ingest_lag_s: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    """İnteqrasiya parametrləri (məs. EnsembleData tokeni və hesab siyahıları). Token API-də heç vaxt geri qaytarılmır."""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------- DGK Structure & Management, açar sözlər
class OrgUnit(Base):
    __tablename__ = "org_units"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(16))  # leadership | aparat | territorial | specialized
    variants: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_url: Mapped[str | None] = mapped_column(String(512))
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Person(Base):
    """Yalnız DGK-dakı xidməti vəzifə konteksti. Şəxsi həyat, reputasiya balı və profil saxlanılmır."""
    __tablename__ = "persons"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(256), unique=True)  # "Soyad Ad Ata adı oğlu"
    surname: Mapped[str] = mapped_column(String(64))
    given_name: Mapped[str] = mapped_column(String(64))
    patronymic: Mapped[str | None] = mapped_column(String(64))
    # {"az": [...], "ascii": [...], "ru": [...], "en": [...], "tr": [...], "auto": true}
    variants: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Position(Base):
    """Vəzifə tarixçəsi. Köhnə xəbərdə adı çəkilən şəxs həmin tarixdəki vəzifəsi ilə əlaqələndirilir."""
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24))  # təsdiqlənmiş | yoxlanmalıdır | keçmiş rəhbər
    source_url: Mapped[str | None] = mapped_column(String(512))
    source_type: Mapped[str] = mapped_column(String(16))  # official | official_news | media | user
    note: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    person: Mapped[Person] = relationship()
    unit: Mapped[OrgUnit | None] = relationship()


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    variants: Mapped[list[str]] = mapped_column(JSONB, default=list)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"))
    unit_inferred: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str | None] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Keyword(Base):
    """İdarə olunan açar söz lüğəti. L1 güclü, L2 kontekstual, L3 zəif (tək başına heç vaxt kifayət etmir)."""
    __tablename__ = "keywords"
    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(256))
    level: Mapped[str] = mapped_column(String(2), index=True)  # L1 | L2 | L3 | EX (istisna)
    category: Mapped[str] = mapped_column(String(32))  # institution | structure | operation | digital | violation | foreign | noise
    lang: Mapped[str] = mapped_column(String(8), default="az")
    variants: Mapped[list[str]] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EntityMention(Base):
    """Xəbərdə qurum strukturu / məntəqə / rəhbər adının DGK kontekstində çəkilməsi."""
    __tablename__ = "entity_mentions"
    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_items.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(16), index=True)  # unit | checkpoint | person
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    matched_text: Mapped[str] = mapped_column(String(256))
    # person üçün: xəbər tarixində etibarlı vəzifə (köhnə xəbər hazırkı vəzifə ilə qarışdırılmır)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))
    context_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    snippet: Mapped[str | None] = mapped_column(Text)
