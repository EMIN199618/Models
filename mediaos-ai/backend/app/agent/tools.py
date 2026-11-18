"""AI Analyst agentinin alətləri.

Hər alət:
  * Pydantic sxemi ilə arqument yoxlaması (schema validation)
  * Rol əsaslı icazə (permission)
  * Sərt timeout
  * `tool_calls` cədvəlində audit
Alətlər YALNIZ oxuyur. Yeganə istisna `generate_report` — o da yalnız `pending_approval`
statuslu qaralama yaradır; dərc insan təsdiqi ilə olur. Silmə/yeniləmə/xarici ötürmə aləti yoxdur.
"""
from __future__ import annotations

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, func, or_, select

from app.cache.redis_cache import get_cache, make_key
from app.chains.base import structured_step
from app.chains.news import risk_chain
from app.chains.report import period_bounds, report_chain
from app.config import get_settings
from app.db import session_scope
from app.llm.prompts import registry as P
from app.models import NewsAnalysis, NewsItem, Report, ReviewItem, Source, ToolCallLog
from app.rag.retriever import PgVectorRetriever, format_context, rerank
from app.text import normalize_az, sanitize_source, stem, tokens

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool")
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass
class ToolContext:
    user_id: int
    role: str
    conversation_id: uuid.UUID | None = None
    refs: dict[str, dict[str, Any]] = field(default_factory=dict)  # bu söhbətdə alətlərin qaytardığı mənbələr


# ------------------------------------------------------------------ sxemlər
DateStr = str


class Period(BaseModel):
    date_from: DateStr | None = Field(default=None, description="YYYY-MM-DD")
    date_to: DateStr | None = Field(default=None, description="YYYY-MM-DD")

    def bounds(self) -> tuple[datetime, datetime]:
        today = date.today()
        df = self.date_from or (today - timedelta(days=29)).isoformat()
        dt = self.date_to or today.isoformat()
        return period_bounds(df, dt)


class SearchNewsArgs(Period):
    query: str | None = Field(default=None, max_length=200)
    content_type: Literal["official", "media", "public_opinion"] | None = None
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    category: str | None = None
    location: str | None = None
    min_risk: Literal["low", "medium", "high"] | None = None
    limit: int = Field(default=10, ge=1, le=30)


class OfficialArgs(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    claim: str | None = Field(default=None, max_length=1000, description="Yoxlanılacaq iddia (varsa)")


class SemanticArgs(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=10)
    doc_types: list[str] | None = None


class CompareArgs(Period):
    query: str = Field(min_length=2, max_length=500)


class SentimentArgs(BaseModel):
    news_id: int | None = None
    text: str | None = Field(default=None, max_length=4000)


class RiskArgs(BaseModel):
    news_id: int


class TrendsArgs(Period):
    group_by: Literal["day", "category", "sentiment", "source", "content_type", "location"] = "day"
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    location: str | None = None


class ReportArgs(Period):
    pass


# ------------------------------------------------------------------ köməkçilər
def _news_row(n: NewsItem) -> dict[str, Any]:
    a = n.analysis
    return {"ref": f"N{n.id}", "news_id": n.id, "title": n.title, "source": n.source.name,
            "date": n.published_at.isoformat(), "content_type": n.content_type, "url": n.url,
            "category": a.category if a else None, "sentiment": a.sentiment if a else None,
            "risk_level": a.risk_level if a else None, "risk_status": a.risk_status if a else None,
            "location": a.location if a else None}


def _period_str(df: datetime, dt: datetime) -> str:
    return f"{df.date()} — {dt.date()}"


# ------------------------------------------------------------------ alətlər
def search_news(ctx: ToolContext, a: SearchNewsArgs) -> dict[str, Any]:
    df, dt = a.bounds()

    def load():
        with session_scope() as db:
            q = (select(NewsItem).join(NewsAnalysis).join(Source)
                 .where(NewsItem.status == "relevant", NewsItem.published_at.between(df, dt)))
            if a.content_type:
                q = q.where(NewsItem.content_type == a.content_type)
            if a.sentiment:
                q = q.where(NewsAnalysis.sentiment == a.sentiment)
            if a.category:
                q = q.where(NewsAnalysis.category == a.category)
            if a.location:
                loc = stem(normalize_az(a.location))
                q = q.where(or_(func.lower(NewsAnalysis.location).like(f"%{loc}%"),
                                func.lower(NewsItem.body).like(f"%{loc}%"), func.lower(NewsItem.title).like(f"%{loc}%")))
            if a.min_risk:
                allowed = [k for k, v in RISK_ORDER.items() if v >= RISK_ORDER[a.min_risk]]
                q = q.where(NewsAnalysis.risk_level.in_(allowed))
            if a.query:
                terms = [stem(t) for t in tokens(a.query)][:6]
                if terms:
                    q = q.where(or_(*[func.lower(NewsItem.title + " " + NewsItem.body).like(f"%{t}%") for t in terms]))
            rows = db.scalars(q.order_by(NewsItem.published_at.desc()).limit(a.limit)).all()
            return [_news_row(n) for n in rows]

    items, cache_state = get_cache().get_or_set("search", make_key("search_news", a.model_dump()),
                                                get_settings().cache_ttl_search, load, scope=f"role:{ctx.role}")
    return {"items": items, "period": _period_str(df, dt), "cache": cache_state}


FACT = None


def search_official_sources(ctx: ToolContext, a: OfficialArgs) -> dict[str, Any]:
    global FACT
    docs = PgVectorRetriever(role=ctx.role, k=10, doc_types=["official_news", "official_doc", "legislation"]).invoke(a.query)
    docs = rerank(a.query, docs, final_k=4, prefer_official=True, min_score=0.25)
    # Söhbət daxilində unikal identifikatorlar (S1, S2, ... alətlər arasında təkrarlanmır)
    start = len([k for k in ctx.refs if k.startswith("S")])
    ctx_text, renamed = format_context(docs, start=start + 1)
    items = [{"ref": k, "title": d.metadata["title"], "source": d.metadata["source"], "doc_type": d.metadata["doc_type"],
              "date": d.metadata.get("published_at"), "score": d.metadata.get("rerank_score"),
              "excerpt": d.page_content[:300]} for k, d in renamed.items()]
    out: dict[str, Any] = {"items": items}
    if a.claim:
        if FACT is None:
            FACT = structured_step(P.FACT_CHECK, "factcheck", on_fail={"status": "unverified", "explanation": "yoxlama aparılmadı"})
        fc = FACT.invoke({"claim": sanitize_source(a.claim, 1000), "evidence": ctx_text or "(rəsmi mənbə tapılmadı)"})
        fc_ids = [e for e in fc.evidence_ids if e in renamed]
        out["verification"] = {"status": fc.status, "evidence_ids": fc_ids, "explanation": fc.explanation,
                               "confidence": fc.confidence}
    return out


def semantic_search(ctx: ToolContext, a: SemanticArgs) -> dict[str, Any]:
    docs = PgVectorRetriever(role=ctx.role, k=max(10, a.k * 2), doc_types=a.doc_types).invoke(a.query)
    docs = rerank(a.query, docs, final_k=a.k, min_score=0.15)
    start = len([k for k in ctx.refs if k.startswith("S")])
    items = []
    for i, d in enumerate(docs, start + 1):
        m = d.metadata
        items.append({"ref": f"N{m['news_id']}" if m.get("news_id") else f"S{i}", "title": m["title"], "source": m["source"],
                      "doc_type": m["doc_type"], "date": m.get("published_at"), "score": m.get("rerank_score"),
                      "content_type": m.get("content_type"), "sentiment": m.get("sentiment")})
    return {"items": items}


def compare_news(ctx: ToolContext, a: CompareArgs) -> dict[str, Any]:
    df, dt = a.bounds()
    docs = PgVectorRetriever(role=ctx.role, k=20, doc_types=["official_news", "media", "monitoring"],
                             date_from=df, date_to=dt).invoke(a.query)
    docs = rerank(a.query, docs, final_k=10, min_score=0.2)
    by_src: dict[str, dict[str, Any]] = {}
    for d in docs:
        m = d.metadata
        if m["source"] in by_src or not m.get("news_id"):
            continue
        by_src[m["source"]] = {"source": m["source"], "title": m["title"], "ref": f"N{m['news_id']}",
                               "content_type": m.get("content_type") or m["doc_type"], "sentiment": m.get("sentiment"),
                               "date": m.get("published_at"), "title_for_ref": m["title"], "doc_type": m["doc_type"]}
    comp = list(by_src.values())
    return {"comparison": comp, "period": _period_str(df, dt),
            "note": "Mənbələr eyni hadisəni fərqli təqdim edə bilər; rəsmi mövqe yalnız official növlü mənbədədir." if comp else
            "Bu mövzu üzrə müqayisə üçün kifayət qədər mənbə tapılmadı."}


SENT = None


def analyze_sentiment(ctx: ToolContext, a: SentimentArgs) -> dict[str, Any]:
    global SENT
    if SENT is None:
        SENT = structured_step(P.SENTIMENT, "tool_sentiment", on_fail={"sentiment": "neutral", "score": 0, "rationale": "-"})
    if a.news_id:
        with session_scope() as db:
            n = db.get(NewsItem, a.news_id)
            if not n:
                return {"error": "xəbər tapılmadı"}
            title, body, ctype, ref = n.title, n.body, n.content_type, f"N{n.id}"
    elif a.text:
        title, body, ctype, ref = "", a.text, "media", None
    else:
        return {"error": "news_id və ya text lazımdır"}
    r = SENT.invoke({"title": sanitize_source(title, 500), "body": sanitize_source(body), "content_type": ctype})
    return {"sentiment": r.model_dump(), "ref": ref,
            "note": "Sentiment risk deyil — risk ayrıca qiymətləndirilir."}


def assess_risk(ctx: ToolContext, a: RiskArgs) -> dict[str, Any]:
    with session_scope() as db:
        n = db.get(NewsItem, a.news_id)
        if not n or not n.analysis:
            return {"error": "xəbər tapılmadı"}
        inp = {"title": n.title, "body": n.body, "content_type": n.content_type,
               "sentiment": n.analysis.sentiment or "neutral",
               "mentions": 1 + db.scalar(select(func.count()).where(NewsItem.dup_of_id == n.id))}
        current = {"level": n.analysis.risk_level, "status": n.analysis.risk_status}
    r = risk_chain().invoke(inp)
    return {"ref": f"N{a.news_id}", "assessment": r.result.model_dump(), "status": r.status, "rule_notes": r.rule_notes,
            "stored": current, "note": "İlkin qiymətləndirmədir; risk siqnalının təsdiqi insan qərarı tələb edir."}


def get_trends(ctx: ToolContext, a: TrendsArgs) -> dict[str, Any]:
    df, dt = a.bounds()
    col = {
        "day": func.to_char(func.date_trunc("day", NewsItem.published_at), "YYYY-MM-DD"),
        "category": NewsAnalysis.category, "sentiment": NewsAnalysis.sentiment, "source": Source.name,
        "content_type": NewsItem.content_type, "location": NewsAnalysis.location,
    }[a.group_by]

    def load():
        with session_scope() as db:
            q = (select(col, func.count()).select_from(NewsItem).join(NewsAnalysis).join(Source)
                 .where(NewsItem.status == "relevant", NewsItem.published_at.between(df, dt)))
            if a.sentiment:
                q = q.where(NewsAnalysis.sentiment == a.sentiment)
            if a.location:
                q = q.where(func.lower(NewsAnalysis.location).like(f"%{stem(normalize_az(a.location))}%"))
            rows = db.execute(q.group_by(col).order_by(func.count().desc())).all()
            return {str(k): int(v) for k, v in rows if k is not None}

    trends, state = get_cache().get_or_set("trends", make_key(a.model_dump()), get_settings().cache_ttl_dashboard, load)
    return {"trends": trends, "group_by": a.group_by, "period": _period_str(df, dt), "cache": state}


def generate_report(ctx: ToolContext, a: ReportArgs) -> dict[str, Any]:
    df, dt = a.bounds()
    r = report_chain().invoke({"date_from": df, "date_to": dt})
    with session_scope() as db:
        rep = Report(title=r["title"], body=r["body"], citations=r["citations"], period_from=df, period_to=dt,
                     status="pending_approval", created_by=ctx.user_id)
        db.add(rep)
        db.flush()
        db.add(ReviewItem(kind="report", report_id=rep.id, payload={"title": rep.title}))
        rid = rep.id
    return {"report": {"id": rid, "title": r["title"], "body": r["body"], "status": "pending_approval"},
            "citations": r["citations"], "period": _period_str(df, dt)}


# ------------------------------------------------------------------ reyestr
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: type[BaseModel]
    fn: Callable[[ToolContext, Any], dict[str, Any]]
    roles: frozenset[str]


ALL = frozenset({"viewer", "analyst", "admin"})
ANALYST = frozenset({"analyst", "admin"})

TOOLS: dict[str, ToolSpec] = {t.name: t for t in [
    ToolSpec("search_news", "DGK xəbərlərini tarix, mövzu, növ (official/media/public_opinion), sentiment, yer və risk üzrə axtarır.", SearchNewsArgs, search_news, ALL),
    ToolSpec("search_official_sources", "Rəsmi DGK mənbələrində (xəbər, sənəd, qanunvericilik) təsdiqləyici məlumat axtarır; claim verilsə, iddianı yoxlayır.", OfficialArgs, search_official_sources, ALL),
    ToolSpec("semantic_search", "RAG bilik bazasında məzmun oxşarlığı üzrə axtarış (əvvəlki oxşar hadisələr).", SemanticArgs, semantic_search, ALL),
    ToolSpec("compare_news", "Eyni hadisənin müxtəlif mənbələrdə təqdimatını müqayisə edir.", CompareArgs, compare_news, ANALYST),
    ToolSpec("analyze_sentiment", "Xəbərin və ya mətnin DGK-yə münasibətdə tonallığını qiymətləndirir.", SentimentArgs, analyze_sentiment, ANALYST),
    ToolSpec("assess_risk", "Müəyyən meyarlar (R1–R6) üzrə izahlı ilkin risk qiymətləndirməsi verir. Bazanı dəyişmir.", RiskArgs, assess_risk, ANALYST),
    ToolSpec("get_trends", "Tarix, mövzu, sentiment, mənbə və yer üzrə statistika hesablayır.", TrendsArgs, get_trends, ALL),
    ToolSpec("generate_report", "İstinadlı analitik icmal hazırlayır (qaralama; dərc üçün insan təsdiqi lazımdır).", ReportArgs, generate_report, ANALYST),
]}


def langchain_tools(role: str) -> list[StructuredTool]:
    """LLM-ə yalnız istifadəçinin roluna icazəli alətlər təqdim olunur."""
    out = []
    for t in TOOLS.values():
        if role in t.roles:
            out.append(StructuredTool.from_function(func=lambda **kw: kw, name=t.name, description=t.description,
                                                    args_schema=t.schema))
    return out


def execute_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    status, err, result = "ok", None, None
    spec = TOOLS.get(name)
    try:
        if spec is None:
            status, err = "invalid", f"naməlum alət: {name}"
        elif ctx.role not in spec.roles:
            status, err = "denied", f"'{ctx.role}' rolu '{name}' alətindən istifadə edə bilməz"
        else:
            parsed = spec.schema.model_validate(args)
            fut = _pool.submit(spec.fn, ctx, parsed)
            result = fut.result(timeout=get_settings().tool_timeout_s)
            if result.get("error"):
                status, err = "error", result["error"]
    except ValidationError as exc:
        status, err = "invalid", f"arqumentlər sxemə uyğun deyil: {exc.errors()[0]['msg']}"
    except FutTimeout:
        status, err = "timeout", f"alət {get_settings().tool_timeout_s}s ərzində cavab vermədi"
    except Exception as exc:
        status, err = "error", f"{type(exc).__name__}: {str(exc)[:200]}"
    latency = (time.perf_counter() - t0) * 1000
    with session_scope() as db:
        db.add(ToolCallLog(user_id=ctx.user_id, conversation_id=ctx.conversation_id, tool=name,
                           args=json.loads(json.dumps(args, default=str)), status=status, latency_ms=latency, error=err))
    if status != "ok":
        return {"tool": name, "error": err, "status": status}
    assert result is not None
    for it in result.get("items", []) + result.get("comparison", []) + result.get("citations", []):
        if "ref" in it:
            ctx.refs[it["ref"]] = it
    v = result.get("verification")
    if v:
        for e in v.get("evidence_ids", []):
            ctx.refs.setdefault(e, {"ref": e})
    return {"tool": name, "status": "ok", **result}
