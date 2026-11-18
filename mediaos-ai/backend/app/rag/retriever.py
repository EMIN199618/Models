"""pgvector əsaslı LangChain Retriever + reranker.

Giriş icazəsi sorğu səviyyəsində tətbiq olunur: istifadəçinin rolu `access_roles` massivində
olmayan və ya təsdiqlənməmiş sənədlər heç vaxt LLM kontekstinə düşmür.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever
from sqlalchemy import text

from app.config import get_settings
from app.db import session_scope
from app.llm.embeddings import get_embeddings
from app.text import stems


class PgVectorRetriever(BaseRetriever):
    role: str = "viewer"
    k: int = 8
    doc_types: list[str] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    approved_only: bool = True

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[LCDocument]:
        qv = get_embeddings().embed_query(query)
        where = [":role = ANY(d.access_roles)"]
        params: dict[str, Any] = {"q": str(qv), "role": self.role, "k": self.k}
        if self.approved_only:
            where.append("d.approval_status = 'approved'")
        if self.doc_types:
            where.append("d.doc_type = ANY(:dt)")
            params["dt"] = self.doc_types
        if self.date_from:
            where.append("d.published_at >= :df")
            params["df"] = self.date_from
        if self.date_to:
            where.append("d.published_at <= :dto")
            params["dto"] = self.date_to
        sql = text(f"""
            SELECT c.id, c.document_id, c.text, c.meta, d.title, d.source, d.doc_type, d.published_at, d.url,
                   d.news_id, 1 - (c.embedding <=> CAST(:q AS vector)) AS score
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE {' AND '.join(where)}
            ORDER BY c.embedding <=> CAST(:q AS vector)
            LIMIT :k
        """)
        with session_scope() as db:
            rows = db.execute(sql, params).mappings().all()
        return [LCDocument(page_content=r["text"], metadata={
            "chunk_id": r["id"], "document_id": r["document_id"], "title": r["title"], "source": r["source"],
            "doc_type": r["doc_type"], "published_at": r["published_at"].isoformat() if r["published_at"] else None,
            "url": r["url"], "news_id": r["news_id"], "vector_score": float(r["score"]), **(r["meta"] or {}),
        }) for r in rows]


def rerank(query: str, docs: list[LCDocument], final_k: int | None = None, min_score: float | None = None,
           prefer_official: bool = False) -> list[LCDocument]:
    """Hibrid yenidən sıralama: vektor oxşarlığı + leksik üst-üstə düşmə + mənbə növü.
    Eyni sənəddən ən çox 2 parça saxlanılır (müxtəliflik)."""
    s = get_settings()
    final_k = final_k or s.rag_final_k
    min_score = s.rag_min_score if min_score is None else min_score
    qs = stems(query)
    scored = []
    for d in docs:
        lex = len(qs & stems(d.page_content)) / max(1, len(qs))
        official = 1.0 if d.metadata.get("doc_type", "").startswith(("official", "legislation")) else 0.0
        score = 0.55 * d.metadata.get("vector_score", 0) + 0.35 * lex + (0.1 * official if prefer_official else 0.0)
        d.metadata["rerank_score"] = round(score, 4)
        d.metadata["lexical"] = round(lex, 4)
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    out, per_doc = [], {}
    for score, d in scored:
        if score < min_score:
            continue
        did = d.metadata["document_id"]
        if per_doc.get(did, 0) >= 2:
            continue
        per_doc[did] = per_doc.get(did, 0) + 1
        out.append(d)
        if len(out) >= final_k:
            break
    return out


def format_context(docs: list[LCDocument], prefix: str = "S", start: int = 1) -> tuple[str, dict[str, LCDocument]]:
    """LLM üçün identifikatorlu kontekst blokları: [S1] (doc_type=..; source=..; date=..)."""
    refs: dict[str, LCDocument] = {}
    parts = []
    for i, d in enumerate(docs, start):
        rid = f"{prefix}{i}"
        refs[rid] = d
        m = d.metadata
        title = str(m.get("title") or "").replace(";", ",").replace("(", "«").replace(")", "»")
        parts.append(f"[{rid}] (doc_type={m.get('doc_type')}; source={m.get('source')}; "
                     f"date={(m.get('published_at') or '')[:10]}; title={title})\n{d.page_content}")
    return "\n---\n".join(parts), refs
