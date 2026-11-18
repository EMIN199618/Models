"""Xəbər emalı zəncirləri (LCEL).

Chain 1 — DGK Relevance:   News Input → Validation → Prompt → LLM → Structured Output → Relevance Decision
Chain 2 — Classification:  Verified Input → (Category ‖ Sentiment) → Structured Output
Chain 3 — Risk Assessment: News + Evidence → Risk Prompt → LLM → Rule Validation → Risk Assessment
"""
from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import Runnable, RunnableLambda, RunnableParallel, RunnablePassthrough
from pydantic import BaseModel, Field

from app.chains.base import structured_step
from app.config import get_settings
from app.llm.prompts import registry as P
from app.llm.schemas import CategoryOutput, RelevanceOutput, RiskOutput, SentimentOutput
from app.rag.retriever import PgVectorRetriever, format_context, rerank
from app.text import sanitize_source


class NewsInput(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    body: str = Field(min_length=10)
    source_name: str
    source_kind: Literal["official", "media", "social", "complaint"]


class RelevanceDecision(BaseModel):
    result: RelevanceOutput
    decision: Literal["accept", "reject", "review"]
    lexicon: dict[str, Any] = Field(default_factory=dict)
    rule_notes: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------- Chain 1
# Keyword Matching → Entity Recognition → Semantic Relevance (LLM) → Rule-based merge → Decision
def _validate(x: dict[str, Any]) -> dict[str, Any]:
    n = NewsInput.model_validate(x)
    return {"title": sanitize_source(n.title, 500), "body": sanitize_source(n.body),
            "source_name": n.source_name, "source_kind": n.source_kind, "published_at": x.get("published_at")}


def _keywords(x: dict[str, Any]) -> dict[str, Any]:
    from app.intel.lexicon import match
    m = match(x["title"], x["body"], x["source_kind"], x.get("published_at"))
    signals = (f"səviyyə={m.level}; bal={m.score}; açar sözlər={', '.join(m.matched_keywords[:8]) or '—'}; "
               f"varlıqlar={', '.join(m.matched_entities[:6]) or '—'}" + ("; XARİCİ GÖMRÜK" if m.foreign else ""))
    return {**x, "_lex": m.as_dict(), "signals": signals}


def _decide(x: dict[str, Any]) -> RelevanceDecision:
    """LLM qərarı ilə lüğət sübutunu açıq qaydalarla birləşdirir."""
    r: RelevanceOutput = x["llm"]
    lx = x["_lex"]
    thr = get_settings().review_confidence_threshold
    notes: list[str] = []
    upd = {"relevance_level": r.relevance_level or lx["level"],
           "matched_keywords": list(dict.fromkeys(r.matched_keywords + lx["matched_keywords"])),
           "matched_entities": list(dict.fromkeys(r.matched_entities + lx["matched_entities"])),
           "evidence": list(dict.fromkeys(r.evidence + lx["evidence"]))[:8],
           "responsibility": r.responsibility or lx["responsibility"]}
    if lx["foreign"] and lx["level"] == "NONE":
        d = "reject"
        notes.append("qayda: başqa ölkənin gömrük orqanı, Azərbaycan/DGK konteksti yoxdur")
        upd["is_relevant"] = False
    elif r.is_relevant and lx["level"] in ("NONE", "WEAK"):
        d = "review"
        notes.append("qayda: model aid hesab edir, amma lüğətdə L1/L2 sübut yoxdur — insan yoxlaması")
    elif not r.is_relevant and lx["decision"] == "PUBLISH" and r.confidence >= thr:
        d = "review"
        notes.append("qayda: lüğətdə güclü sübut var, model rədd edir — insan yoxlaması")
    elif lx["decision"] == "REVIEW" and r.is_relevant:
        d = "review"
        notes.append("qayda: yalnız kontekstual/semantik əlaqə — yoxlanmalıdır")
    elif r.confidence < thr:
        d = "review"
    else:
        d = "accept" if r.is_relevant else "reject"
    return RelevanceDecision(result=r.model_copy(update=upd), decision=d, lexicon=lx, rule_notes=notes)


def relevance_chain() -> Runnable:
    llm = structured_step(P.RELEVANCE, "relevance", on_fail={
        "is_relevant": False, "score": 0.5, "content_type": "media", "reason": "model cavabı alınmadı"})
    return (RunnableLambda(_validate, name="validate_input")
            | RunnableLambda(_keywords, name="keyword_entity_matching")
            | RunnablePassthrough.assign(llm=llm)
            | RunnableLambda(_decide, name="relevance_decision")).with_config(run_name="chain1_relevance")


# ----------------------------------------------------------------- Chain 2
class Classification(BaseModel):
    category: CategoryOutput
    sentiment: SentimentOutput


def classification_chain() -> Runnable:
    cat = structured_step(P.CATEGORY, "classification", on_fail={"category": "other"})
    sent = structured_step(P.SENTIMENT, "classification", on_fail={"sentiment": "neutral", "score": 0, "rationale": "model cavabı alınmadı"})
    # Kateqoriya və sentiment bir-birindən asılı deyil → paralel işləyir
    return (RunnableLambda(lambda x: {**x, "title": sanitize_source(x["title"], 500), "body": sanitize_source(x["body"])},
                           name="prepare_verified")
            | RunnableParallel(category=cat, sentiment=sent)
            | RunnableLambda(lambda r: Classification(**r), name="merge")).with_config(run_name="chain2_classification")


# ----------------------------------------------------------------- Chain 3
OFFICIAL_TYPES = ["official_news", "official_doc", "legislation"]


def _evidence(x: dict[str, Any]) -> dict[str, Any]:
    q = f"{x['title']} {x['body'][:400]}"
    docs = PgVectorRetriever(role="admin", k=10, doc_types=OFFICIAL_TYPES).invoke(q)
    docs = rerank(q, docs, final_k=3, prefer_official=True)
    ctx, refs = format_context(docs, prefix="E")
    return {"evidence": ctx or "(rəsmi sübut tapılmadı)", "_evidence_refs": {k: v.metadata for k, v in refs.items()}}


class RiskAssessment(BaseModel):
    result: RiskOutput
    status: Literal["auto", "pending_review"]
    rule_notes: list[str] = Field(default_factory=list)
    evidence: dict[str, dict[str, Any]] = Field(default_factory=dict)


SEVERE = {"R1", "R2", "R4", "R5"}


def validate_risk(x: dict[str, Any]) -> RiskAssessment:
    """Qayda əsaslı yoxlama — LLM nəticəsini məcburi prinsiplərlə uyğunlaşdırır."""
    r: RiskOutput = x["llm"]
    refs: dict[str, Any] = x.get("_evidence_refs", {})
    notes: list[str] = []
    upd: dict[str, Any] = {}
    # 1) Uydurma sübut identifikatorlarını sil
    valid_ev = [e for e in r.evidence_ids if e in refs]
    if len(valid_ev) != len(r.evidence_ids):
        notes.append(f"kontekstdə olmayan sübut id-ləri silindi: {sorted(set(r.evidence_ids) - set(valid_ev))}")
        upd["evidence_ids"] = valid_ev
    crit = set(r.criteria)
    level = r.risk_level
    # 2) high/critical yalnız ağır meyarla
    if level in ("high", "critical") and not (crit & SEVERE):
        level = "medium" if crit else "low"
        notes.append(f"{r.risk_level} səviyyə ağır meyar (R1/R2/R4/R5) olmadan verilə bilməz — endirildi")
    # 3) critical yalnız geniş yayılma (R6) və təsdiq və ya ≥2 ağır meyar ilə
    if level == "critical" and not ("R6" in crit and (r.claim_verified or len(crit & SEVERE) >= 2)):
        level = "high"
        notes.append("critical üçün geniş yayılma və təsdiqlənmiş/çoxsaylı ağır meyar lazımdır — high")
    # 4) Mənfi sentiment tək başına risk deyil
    if level not in ("low", "none") and not crit:
        level = "low"
        notes.append("meyar göstərilməyib; yalnız mənfi tonallıq risk sayılmır — low")
    # 5) Rəsmi adi məlumat risk yaratmır
    if x.get("content_type") == "official" and not (crit & SEVERE) and level != "none":
        level = "none"
        notes.append("rəsmi məlumat, ağır meyar yoxdur — maddi risk aşkarlanmayıb")
    upd["risk_level"] = level
    review = level in ("high", "critical") or (level == "medium" and not r.claim_verified) or \
        r.confidence < get_settings().review_confidence_threshold
    upd["requires_human_review"] = review
    result = r.model_copy(update=upd)
    return RiskAssessment(result=result, status="pending_review" if review else "auto", rule_notes=notes,
                          evidence={k: v for k, v in refs.items() if k in result.evidence_ids})


def risk_chain(with_evidence: bool = True) -> Runnable:
    llm = structured_step(P.RISK, "risk", on_fail={"risk_level": "low", "score": 0.0, "requires_human_review": True,
                                                   "reasons": ["model cavabı alınmadı"]})
    prep = RunnableLambda(lambda x: {**x, "title": sanitize_source(x["title"], 500), "body": sanitize_source(x["body"]),
                                     "mentions": x.get("mentions", 1), "reach": x.get("reach", "—")}, name="prepare_risk")
    ev = RunnablePassthrough.assign(**{"_ev": RunnableLambda(_evidence, name="retrieve_official_evidence")}) if with_evidence \
        else RunnablePassthrough.assign(_ev=RunnableLambda(lambda _: {"evidence": "", "_evidence_refs": {}}))
    flatten = RunnableLambda(lambda x: {**{k: v for k, v in x.items() if k != "_ev"}, **x["_ev"]}, name="flatten_evidence")
    return (prep | ev | flatten | RunnablePassthrough.assign(llm=llm)
            | RunnableLambda(validate_risk, name="rule_validation")).with_config(run_name="chain3_risk")
