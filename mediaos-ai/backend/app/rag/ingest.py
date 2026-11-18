"""RAG ingestion pipeline:
Document Loader → Cleaning → Metadata → Chunking → Embeddings → pgvector.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm.embeddings import get_embeddings
from app.models import Chunk, Document, NewsAnalysis, NewsItem
from app.text import clean_text, content_hash

log = logging.getLogger(__name__)

DOC_TYPES = {"official_news", "official_doc", "legislation", "media", "monitoring", "internal"}
REQUIRED_META = ("title", "source", "doc_type")


class NewsItemLoader(BaseLoader):
    """DGK-yə aid (relevant) xəbərləri RAG sənədlərinə çevirir. Hələ indekslənməyənləri yükləyir."""

    def __init__(self, db: Session, only_unindexed: bool = True, limit: int = 1000):
        self.db, self.only_unindexed, self.limit = db, only_unindexed, limit

    def lazy_load(self) -> Iterator[LCDocument]:
        q = select(NewsItem).where(NewsItem.status == "relevant").order_by(NewsItem.id).limit(self.limit)
        if self.only_unindexed:
            q = q.where(~select(Document.id).where(Document.news_id == NewsItem.id).exists())
        for n in self.db.scalars(q):
            a: NewsAnalysis | None = n.analysis
            doc_type = "official_news" if n.content_type == "official" else "media" if n.content_type == "media" else "monitoring"
            yield LCDocument(page_content=f"{n.title}. {n.body}", metadata={
                "title": n.title, "source": n.source.name, "url": n.url, "doc_type": doc_type,
                "published_at": n.published_at.isoformat(), "news_id": n.id, "content_type": n.content_type,
                "sentiment": a.sentiment if a else None, "category": a.category if a else None,
                "approval_status": "approved",
            })


class FrontMatterDirectoryLoader(BaseLoader):
    """Qovluqdan .md/.txt sənədləri yükləyir. Faylın başında `key: value` metadata bloku olur:

        ---
        title: Gömrük Məcəlləsi, maddə 12
        source: DGK rəsmi saytı
        doc_type: legislation
        published_at: 2026-01-15
        approval_status: approved
        access_roles: viewer,analyst,admin
        ---
        mətn...
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def lazy_load(self) -> Iterator[LCDocument]:
        for f in sorted(self.path.rglob("*")):
            if f.suffix not in (".md", ".txt"):
                continue
            raw = f.read_text(encoding="utf-8")
            meta: dict[str, Any] = {"file": str(f.name)}
            m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
            if m:
                for line in m.group(1).splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
                raw = m.group(2)
            if "access_roles" in meta and isinstance(meta["access_roles"], str):
                meta["access_roles"] = [r.strip() for r in meta["access_roles"].split(",") if r.strip()]
            yield LCDocument(page_content=raw, metadata=meta)


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    dt = datetime.fromisoformat(str(v))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def ingest_documents(db: Session, docs: list[LCDocument]) -> dict[str, int]:
    """Sənədləri təmizləyir, yoxlayır, chunk-lara bölür, embed edir və saxlayır. İdempotentdir."""
    s = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.rag_chunk_size, chunk_overlap=s.rag_chunk_overlap,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )
    emb = get_embeddings()
    stats = {"loaded": len(docs), "inserted": 0, "skipped_duplicate": 0, "rejected_metadata": 0, "chunks": 0}
    for d in docs:
        text = clean_text(d.page_content)
        meta = d.metadata
        if not text or any(not meta.get(k) for k in REQUIRED_META) or meta.get("doc_type") not in DOC_TYPES:
            stats["rejected_metadata"] += 1
            log.warning("Sənəd rədd edildi (metadata natamamdır): %s", meta.get("title") or meta.get("file"))
            continue
        h = content_hash(meta["title"], text)
        if db.scalar(select(Document.id).where(Document.content_hash == h)):
            stats["skipped_duplicate"] += 1
            continue
        doc = Document(
            title=meta["title"], source=meta["source"], url=meta.get("url"), doc_type=meta["doc_type"],
            published_at=_parse_dt(meta.get("published_at")),
            approval_status=meta.get("approval_status", "pending"),
            access_roles=meta.get("access_roles") or ["viewer", "analyst", "admin"],
            news_id=meta.get("news_id"), content_hash=h,
        )
        db.add(doc)
        db.flush()
        pieces = splitter.split_text(text)
        vectors = emb.embed_documents(pieces)
        extra = {k: meta[k] for k in ("content_type", "sentiment", "category") if meta.get(k)}
        for i, (p, v) in enumerate(zip(pieces, vectors)):
            db.add(Chunk(document_id=doc.id, ord=i, text=p, embedding=v, meta=extra))
        stats["inserted"] += 1
        stats["chunks"] += len(pieces)
    db.flush()
    return stats


def index_relevant_news(db: Session) -> dict[str, int]:
    return ingest_documents(db, list(NewsItemLoader(db).lazy_load()))
