"""Chain 4 — RAG Analysis:
User Question → Retriever → Reranker → Context Builder → LLM → Source Validation → Answer
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from pydantic import BaseModel, Field

from app.chains.base import structured_step
from app.config import get_settings
from app.llm.prompts import registry as P
from app.llm.schemas import RagAnswer
from app.rag.retriever import PgVectorRetriever, format_context, rerank


class SourceRef(BaseModel):
    id: str
    title: str
    source: str
    doc_type: str
    published_at: str | None = None
    url: str | None = None
    news_id: int | None = None
    score: float | None = None


class RagResult(BaseModel):
    answer: str
    citations: list[SourceRef]
    insufficient_evidence: bool
    confidence: float
    period: str
    verification: str = Field(description="official | mixed | unofficial | none")
    validation_notes: list[str] = Field(default_factory=list)


def _retrieve(x: dict[str, Any]) -> list:
    s = get_settings()
    r = PgVectorRetriever(role=x.get("role", "viewer"), k=s.rag_top_k, doc_types=x.get("doc_types"),
                          date_from=x.get("date_from"), date_to=x.get("date_to"))
    return r.invoke(x["question"])


def _rerank(x: dict[str, Any]) -> list:
    prefer = bool(re.search(r"təsdiq|rəsmi|qanun|qayda", x["question"].lower()))
    return rerank(x["question"], x["docs"], prefer_official=prefer)


def _build_context(x: dict[str, Any]) -> dict[str, Any]:
    ctx, refs = format_context(x["ranked"])
    df: datetime | None = x.get("date_from")
    dt: datetime | None = x.get("date_to")
    period = f"{df.date() if df else 'əvvəldən'} — {dt.date() if dt else 'bu günə qədər'}"
    return {**x, "context": ctx or "(uyğun mənbə tapılmadı)", "refs": refs, "period": period}


def validate_sources(x: dict[str, Any]) -> RagResult:
    """Mənbə yoxlaması: cavabdakı hər [S#] kontekstdə mövcud olmalıdır; uydurma istinadlar silinir."""
    ans: RagAnswer = x["llm"]
    refs = x["refs"]
    notes = []
    text = ans.answer
    in_text = set(re.findall(r"\[(S\d+)\]", text))
    bogus = (in_text | set(ans.citations)) - set(refs)
    if bogus:
        notes.append(f"kontekstdə olmayan istinadlar silindi: {sorted(bogus)}")
        for b in bogus:
            text = text.replace(f"[{b}]", "")
    used = [c for c in dict.fromkeys(list(ans.citations) + sorted(in_text)) if c in refs]
    insufficient = ans.insufficient_evidence or not refs
    conf = ans.confidence
    if not insufficient and not used:
        insufficient = True
        conf = min(conf, 0.3)
        notes.append("cavabda etibarlı mənbə istinadı yoxdur — dəlilsiz cavab kimi işarələndi")
        text = ("Mövcud mənbələr əsasında təsdiqlənmiş cavab vermək mümkün olmadı. "
                "Aşağıdakı mətn yoxlanılmamış nəticədir: " + text)
    cites = []
    for c in used:
        m = refs[c].metadata
        cites.append(SourceRef(id=c, title=m["title"], source=m["source"], doc_type=m["doc_type"],
                               published_at=m.get("published_at"), url=m.get("url"), news_id=m.get("news_id"),
                               score=m.get("rerank_score")))
    kinds = {c.doc_type.startswith(("official", "legislation")) for c in cites}
    verification = "none" if not cites else "official" if kinds == {True} else "unofficial" if kinds == {False} else "mixed"
    return RagResult(answer=text.strip(), citations=cites, insufficient_evidence=insufficient, confidence=conf,
                     period=x["period"], verification=verification, validation_notes=notes)


def rag_chain() -> Runnable:
    llm = structured_step(P.RAG_QA, "rag", on_fail={"answer": "Cavab hazırlamaq mümkün olmadı.",
                                                    "insufficient_evidence": True})
    return (
        RunnablePassthrough.assign(docs=RunnableLambda(_retrieve, name="retriever"))
        | RunnablePassthrough.assign(ranked=RunnableLambda(_rerank, name="reranker"))
        | RunnableLambda(_build_context, name="context_builder")
        | RunnablePassthrough.assign(llm=llm)
        | RunnableLambda(validate_sources, name="source_validation")
    ).with_config(run_name="chain4_rag")
