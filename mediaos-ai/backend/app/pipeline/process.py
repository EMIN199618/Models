"""Xəbər emalı pipeline-ı:
Collectors → Validation + Deduplication → DGK Relevance Filter → PostgreSQL → (Classification ‖ Sentiment)
→ Risk → Vector Index → Redis invalidation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.cache.redis_cache import get_cache
from app.chains.news import classification_chain, relevance_chain, risk_chain
from app.llm.prompts.registry import versions
from app.llm.provider import provider_info
from app.models import AuditLog, NewsAnalysis, NewsItem, ReviewItem, Source
from app.rag.ingest import index_relevant_news
from app.text import clean_text, content_hash, simhash

log = logging.getLogger(__name__)
NEAR_DUP_BITS = 6


@dataclass
class RawNews:
    source_name: str
    source_kind: str  # official | media | social | complaint
    title: str
    body: str
    published_at: datetime
    url: str | None = None
    is_synthetic: bool = False
    platform: str | None = None          # tiktok | instagram | None (veb)
    external_id: str | None = None
    author_handle: str | None = None
    engagement: dict[str, Any] = field(default_factory=dict)
    media: list[dict[str, Any]] = field(default_factory=list)


def analysis_text(raw: "RawNews", body: str) -> str:
    """Şəkildəki (OCR) və videodakı (transkript) mətn analizə ayrıca, işarələnmiş blok kimi əlavə olunur."""
    extra = []
    for m in raw.media or []:
        if m.get("ocr_text"):
            extra.append(f"[Şəkildəki mətn (OCR): {m['ocr_text'][:800]}]")
        for seg in (m.get("transcript") or [])[:200]:
            extra.append(f"[Video {seg.get('t', 0):.0f}s: {seg.get('text', '')[:300]}]")
    return body + ("\n" + "\n".join(extra) if extra else "")


def reach_label(eng: dict[str, Any]) -> str:
    """Sosial yayılma: viral hədləri aşılırsa 'viral' işarəsi (risk meyarı R6)."""
    from app.config import get_settings
    if not eng:
        return "—"
    s = get_settings()
    views, shares = int(eng.get("views") or 0), int(eng.get("shares") or 0)
    viral = views >= s.ed_viral_views or shares >= s.ed_viral_shares
    parts = [f"{k}={v}" for k, v in eng.items() if isinstance(v, int) and v]
    return ("viral; " if viral else "") + (", ".join(parts) or "—")


@dataclass
class PipelineStats:
    fetched: int = 0
    invalid: int = 0
    duplicates: int = 0
    near_duplicates: int = 0
    irrelevant: int = 0
    relevant: int = 0
    review: int = 0
    risk_pending: int = 0
    indexed_chunks: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _source(db: Session, name: str, kind: str) -> Source:
    s = db.scalar(select(Source).where(Source.name == name))
    if not s:
        s = Source(name=name, kind=kind, is_official=kind == "official",
                   trust_level={"official": 1.0, "media": 0.6, "social": 0.3, "complaint": 0.3}.get(kind, 0.5))
        db.add(s)
        db.flush()
    return s


def _near_dup(db: Session, sh: int) -> NewsItem | None:
    row = db.execute(text(
        "SELECT id FROM news_items WHERE dup_of_id IS NULL AND bit_count(((simhash # :sh)::bit(64))) <= :b "
        "ORDER BY id LIMIT 1"), {"sh": sh, "b": NEAR_DUP_BITS}).first()
    return db.get(NewsItem, row[0]) if row else None


def process_batch(db: Session, items: list[RawNews], index: bool = True) -> PipelineStats:
    st = PipelineStats(fetched=len(items))
    rel, cls, risk = relevance_chain(), classification_chain(), risk_chain()
    pv = versions()
    model = provider_info()["model"]
    for raw in items:
        title, body = clean_text(raw.title), clean_text(raw.body)
        # ---- Validation
        if len(title) < 3 or len(body) < 10:
            st.invalid += 1
            continue
        pub = raw.published_at if raw.published_at.tzinfo else raw.published_at.replace(tzinfo=timezone.utc)
        h = content_hash(title, body)
        # ---- Exact dedup
        if db.scalar(select(NewsItem.id).where(NewsItem.content_hash == h)) or (
                raw.external_id and db.scalar(select(NewsItem.id).where(
                    NewsItem.platform == raw.platform, NewsItem.external_id == raw.external_id))):
            st.duplicates += 1
            continue
        src = _source(db, raw.source_name, raw.source_kind)
        sh = simhash(f"{title} {body}")
        twin = _near_dup(db, sh)
        # ---- Relevance filter (Chain 1): keyword → entity → semantic → qayda
        body_full = analysis_text(raw, body)
        try:
            dec = rel.invoke({"title": title, "body": body_full, "source_name": src.name, "source_kind": src.kind,
                              "published_at": pub})
        except Exception as exc:
            st.errors.append(f"relevance: {exc}")
            continue
        r = dec.result
        status = {"accept": "relevant", "reject": "irrelevant", "review": "needs_review"}[dec.decision]
        if twin is not None:
            status = "duplicate"
            st.near_duplicates += 1
        n = NewsItem(source_id=src.id, url=raw.url, title=title, body=body, published_at=pub, content_hash=h,
                     simhash=sh, status=status, content_type=r.content_type, dup_of_id=twin.id if twin else None,
                     is_synthetic=raw.is_synthetic, platform=raw.platform, external_id=raw.external_id,
                     author_handle=raw.author_handle, engagement=raw.engagement or {}, media=raw.media or [],
                     language=dec.lexicon.get("language"))
        db.add(n)
        db.flush()
        a = NewsAnalysis(news_id=n.id, is_relevant=r.is_relevant, relevance_score=r.score,
                         relevance_reason="; ".join([r.reason, *dec.rule_notes])[:2000],
                         confidence=r.confidence, prompt_versions={"relevance": pv["dgk_relevance"]}, model=model,
                         relevance_level=r.relevance_level, matched_keywords=r.matched_keywords,
                         matched_entities=r.matched_entities, evidence=r.evidence)
        db.add(a)
        _store_mentions(db, n.id, dec.lexicon)
        if status == "irrelevant":
            st.irrelevant += 1
            continue
        if status == "needs_review":
            st.review += 1
            db.add(ReviewItem(kind="relevance", news_id=n.id, payload={"reason": r.reason, "score": r.score,
                                                                       "confidence": r.confidence, "level": r.relevance_level,
                                                                       "evidence": r.evidence, "rules": dec.rule_notes}))
        if status == "duplicate":
            continue
        # ---- Classification ‖ Sentiment (Chain 2)
        c = cls.invoke({"title": title, "body": body_full, "content_type": r.content_type})
        a.category, a.location = c.category.category, c.category.location
        a.sentiment, a.sentiment_score = c.sentiment.sentiment, c.sentiment.score
        # ---- Risk (Chain 3) — sentimentdən müstəqil meyarlarla
        mentions = 1 + (db.scalar(text("SELECT count(*) FROM news_items WHERE dup_of_id = :i"), {"i": n.id}) or 0)
        ra = risk.invoke({"title": title, "body": body_full, "content_type": r.content_type, "source_kind": src.kind,
                          "sentiment": c.sentiment.sentiment, "mentions": mentions,
                          "reach": reach_label(raw.engagement)})
        a.risk_level, a.risk_score = ra.result.risk_level, ra.result.score
        a.risk_reasons = ra.result.reasons + [f"qayda: {x}" for x in ra.rule_notes]
        a.risk_status = ra.status
        a.confidence = min(r.confidence, c.category.confidence, c.sentiment.confidence, ra.result.confidence)
        a.prompt_versions = {"relevance": pv["dgk_relevance"], "category": pv["news_category"],
                             "sentiment": pv["sentiment"], "risk": pv["risk_assessment"]}
        if ra.status == "pending_review":
            st.risk_pending += 1
            db.add(ReviewItem(kind="risk", news_id=n.id, payload={
                "level": ra.result.risk_level, "criteria": ra.result.criteria, "reasons": ra.result.reasons,
                "verified": ra.result.claim_verified, "evidence": ra.evidence}))
        if status == "relevant":
            st.relevant += 1
    db.flush()
    if index:
        st.indexed_chunks = index_relevant_news(db)["chunks"]
    db.add(AuditLog(action="pipeline.batch", detail=st.as_dict()))
    # Yeni məlumat gəldi → asılı keşləri etibarsız et
    cache = get_cache()
    for ns in ("dashboard", "latest_news", "search", "trends"):
        cache.invalidate(ns)
    return st


def _store_mentions(db: Session, news_id: int, lex: dict[str, Any]) -> None:
    """Struktur, məntəqə və rəhbər adlarının çəkilməsini saxlayır. Yalnız bazadakı (int id) varlıqlar."""
    from app.models import EntityMention
    for u in lex.get("units", []):
        if isinstance(u["id"], int):
            db.add(EntityMention(news_id=news_id, entity_type="unit", entity_id=u["id"], matched_text=u["name"],
                                 context_confirmed=True))
    for c in lex.get("checkpoints", []):
        if isinstance(c["id"], int):
            db.add(EntityMention(news_id=news_id, entity_type="checkpoint", entity_id=c["id"], matched_text=c["name"],
                                 context_confirmed=c["confirmed"]))
    for p in lex.get("persons", []):
        if isinstance(p["id"], int):
            pos = p.get("position") or {}
            db.add(EntityMention(news_id=news_id, entity_type="person", entity_id=p["id"], matched_text=p["matched"][:256],
                                 position_id=pos.get("id"), context_confirmed=p["confirmed"]))
