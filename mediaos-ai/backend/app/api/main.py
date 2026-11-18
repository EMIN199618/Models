"""FastAPI backend: Dashboard API + AI Analyst Chat + yaddaş + insan yoxlaması + metriklər."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session, joinedload
from starlette.concurrency import run_in_threadpool

from app.agent.analyst import run_agent
from app.agent.tools import TOOLS
from app.cache.redis_cache import get_cache, make_key
from app.config import get_settings
from app.db import get_session, init_db, session_scope
from app.llm.prompts.registry import ALL_PROMPTS
from app.llm.provider import provider_info
from app.memory import service as mem
from app.models import (AuditLog, ChatMessage, CollectorRun, Conversation, LLMCallLog, NewsAnalysis, NewsItem, Report,
                        RequestMetric, ReviewItem, Source, ToolCallLog, User)
from app.observability.metrics import percentile
from app.pipeline.process import RawNews, process_batch
from app.rag.ingest import ingest_documents
from app.rag.retriever import PgVectorRetriever, rerank
from app.security.auth import current_user, rate_limited, require_role

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="MEDIA OS AI", version="2.0.0", description="DGK media monitorinqi və AI Analyst API",
              lifespan=lifespan)
FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
_lat: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=2000))


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    t0 = time.perf_counter()
    response: Response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    if path.startswith("/api") or path == "/health":
        _lat[path].append(ms)
        response.headers["X-Response-Time-ms"] = f"{ms:.1f}"

        def _save():
            try:
                with session_scope() as db:
                    db.add(RequestMetric(route=path, method=request.method, status_code=response.status_code,
                                         latency_ms=ms, cache=response.headers.get("X-Cache")))
            except Exception:
                pass
        await run_in_threadpool(_save)
    return response


# ------------------------------------------------------------------ health
@app.get("/health")
def health(db: Session = Depends(get_session)) -> dict[str, Any]:
    db_ok = db.execute(text("SELECT 1")).scalar() == 1
    return {"status": "ok" if db_ok else "degraded", "postgres": db_ok, "redis": get_cache().ping(),
            "llm": provider_info()}


# ------------------------------------------------------------------ dashboard
def _dashboard_stats(days: int) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with session_scope() as db:
        base = (select(NewsItem).join(NewsAnalysis).where(NewsItem.status == "relevant", NewsItem.published_at >= since)).subquery()

        def grp(col):
            rows = db.execute(select(col, func.count()).select_from(NewsItem).join(NewsAnalysis)
                              .where(NewsItem.status == "relevant", NewsItem.published_at >= since)
                              .group_by(col)).all()
            return {str(k): v for k, v in rows if k is not None}

        day = func.to_char(func.date_trunc("day", NewsItem.published_at), "YYYY-MM-DD")
        daily = db.execute(select(day, func.count(), func.sum(case((NewsAnalysis.sentiment == "negative", 1), else_=0)))
                           .select_from(NewsItem).join(NewsAnalysis)
                           .where(NewsItem.status == "relevant", NewsItem.published_at >= since)
                           .group_by(day).order_by(day)).all()
        return {
            "period_days": days,
            "total": db.scalar(select(func.count()).select_from(base)) or 0,
            "by_content_type": grp(NewsItem.content_type),
            "by_sentiment": grp(NewsAnalysis.sentiment),
            "by_category": grp(NewsAnalysis.category),
            "by_risk": grp(NewsAnalysis.risk_level),
            "by_location": grp(NewsAnalysis.location),
            "daily": [{"day": d, "total": t, "negative": int(n or 0)} for d, t, n in daily],
            "pending_review": db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.status == "pending")) or 0,
            "filtered_irrelevant": db.scalar(select(func.count()).select_from(NewsItem).where(
                NewsItem.status == "irrelevant", NewsItem.collected_at >= since)) or 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/dashboard/stats")
def dashboard_stats(response: Response, days: int = Query(7, ge=1, le=365), _: User = Depends(rate_limited())):
    data, state = get_cache().get_or_set("dashboard", make_key(days), get_settings().cache_ttl_dashboard,
                                         lambda: _dashboard_stats(days))
    response.headers["X-Cache"] = state
    return data


def _latest(limit: int, content_type: str | None) -> list[dict[str, Any]]:
    with session_scope() as db:
        q = (select(NewsItem).options(joinedload(NewsItem.source), joinedload(NewsItem.analysis))
             .where(NewsItem.status == "relevant"))
        if content_type:
            q = q.where(NewsItem.content_type == content_type)
        rows = db.scalars(q.order_by(NewsItem.published_at.desc()).limit(limit)).all()
        return [{"id": n.id, "ref": f"N{n.id}", "title": n.title, "source": n.source.name, "url": n.url,
                 "published_at": n.published_at.isoformat(), "content_type": n.content_type,
                 "category": n.analysis.category, "sentiment": n.analysis.sentiment, "risk_level": n.analysis.risk_level,
                 "risk_status": n.analysis.risk_status, "location": n.analysis.location,
                 "is_synthetic": n.is_synthetic} for n in rows]


@app.get("/api/news/latest")
def latest_news(response: Response, limit: int = Query(20, ge=1, le=100),
                content_type: Literal["official", "media", "public_opinion"] | None = None,
                _: User = Depends(rate_limited())):
    data, state = get_cache().get_or_set("latest_news", make_key(limit, content_type),
                                         get_settings().cache_ttl_latest_news, lambda: _latest(limit, content_type))
    response.headers["X-Cache"] = state
    return data


@app.get("/api/news/{news_id}")
def news_detail(news_id: int, db: Session = Depends(get_session), _: User = Depends(rate_limited())):
    n = db.get(NewsItem, news_id)
    if not n:
        raise HTTPException(404, "xəbər tapılmadı")
    a = n.analysis
    return {"id": n.id, "title": n.title, "body": n.body, "source": n.source.name, "url": n.url,
            "published_at": n.published_at, "content_type": n.content_type, "status": n.status,
            "dup_of_id": n.dup_of_id, "is_synthetic": n.is_synthetic,
            "analysis": None if not a else {
                "relevance_score": a.relevance_score, "relevance_reason": a.relevance_reason, "category": a.category,
                "location": a.location, "sentiment": a.sentiment, "sentiment_score": a.sentiment_score,
                "risk_level": a.risk_level, "risk_score": a.risk_score, "risk_reasons": a.risk_reasons,
                "risk_status": a.risk_status, "confidence": a.confidence, "prompt_versions": a.prompt_versions,
                "model": a.model}}


# ------------------------------------------------------------------ semantic search
@app.get("/api/search")
def search(response: Response, q: str = Query(min_length=2, max_length=300), k: int = Query(5, ge=1, le=20),
           user: User = Depends(rate_limited())):
    def load():
        docs = PgVectorRetriever(role=user.role, k=max(10, 2 * k)).invoke(q)
        docs = rerank(q, docs, final_k=k, min_score=0.1)
        return [{"title": d.metadata["title"], "source": d.metadata["source"], "doc_type": d.metadata["doc_type"],
                 "published_at": d.metadata.get("published_at"), "news_id": d.metadata.get("news_id"),
                 "score": d.metadata["rerank_score"], "excerpt": d.page_content[:280]} for d in docs]
    # Nəticə roldan asılıdır (icazəli sənədlər) → açar rol səviyyəsində
    data, state = get_cache().get_or_set("search", make_key("api_search", q.strip().lower(), k),
                                         get_settings().cache_ttl_search, load, scope=f"role:{user.role}")
    response.headers["X-Cache"] = state
    return {"query": q, "results": data}


# ------------------------------------------------------------------ AI Analyst chat
class ChatIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = None


@app.post("/api/chat")
def chat(body: ChatIn, response: Response, db: Session = Depends(get_session),
         user: User = Depends(rate_limited("chat", get_settings().rate_limit_chat_per_minute))):
    try:
        out = run_agent(db, user, body.question, body.conversation_id)
    except PermissionError as exc:
        raise HTTPException(404, str(exc)) from exc
    response.headers["X-Cache"] = "hit" if out.get("cached") else "miss"
    return out


@app.get("/api/conversations/{cid}/messages")
def conversation_messages(cid: str, db: Session = Depends(get_session), user: User = Depends(current_user)):
    try:
        conv = mem.get_or_create_conversation(db, user.id, cid)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(404, "söhbət tapılmadı") from exc
    rows = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv.id).order_by(ChatMessage.id)).all()
    return [{"role": r.role, "content": r.content, "meta": r.meta, "at": r.created_at} for r in rows]


# ------------------------------------------------------------------ memory
class MemoryIn(BaseModel):
    kind: Literal["dashboard_pref", "monitoring_topic", "query_template", "note"]
    key: str = Field(min_length=1, max_length=128)
    value: dict[str, Any]
    ttl_days: int | None = Field(default=None, ge=1, le=730)


@app.get("/api/memory")
def memory_list(db: Session = Depends(get_session), user: User = Depends(current_user)):
    return [{"id": m.id, "kind": m.kind, "key": m.key, "value": m.value, "approved": m.approved,
             "expires_at": m.expires_at} for m in mem.list_memory(db, user.id)]


@app.post("/api/memory", status_code=201)
def memory_propose(body: MemoryIn, db: Session = Depends(get_session), user: User = Depends(current_user)):
    try:
        m = mem.propose_memory(db, user.id, body.kind, body.key, body.value, body.ttl_days)
    except mem.MemoryError_ as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"id": m.id, "approved": m.approved, "note": "Yadda saxlanması üçün təsdiq edin: POST /api/memory/{id}/approve"}


@app.post("/api/memory/{item_id}/approve")
def memory_approve(item_id: int, db: Session = Depends(get_session), user: User = Depends(current_user)):
    try:
        m = mem.approve_memory(db, user.id, item_id)
    except PermissionError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": m.id, "approved": True}


@app.delete("/api/memory/{item_id}", status_code=204)
def memory_delete(item_id: int, db: Session = Depends(get_session), user: User = Depends(current_user)):
    try:
        mem.delete_memory(db, user.id, item_id)
    except PermissionError as exc:
        raise HTTPException(404, str(exc)) from exc


# ------------------------------------------------------------------ human review
@app.get("/api/review")
def review_list(status: str = "pending", kind: str | None = None, db: Session = Depends(get_session),
                _: User = Depends(require_role("analyst"))):
    q = select(ReviewItem).where(ReviewItem.status == status)
    if kind:
        q = q.where(ReviewItem.kind == kind)
    rows = db.scalars(q.order_by(ReviewItem.id.desc()).limit(200)).all()
    out = []
    for r in rows:
        n = db.get(NewsItem, r.news_id) if r.news_id else None
        out.append({"id": r.id, "kind": r.kind, "status": r.status, "payload": r.payload, "created_at": r.created_at,
                    "news": {"id": n.id, "title": n.title, "source": n.source.name, "content_type": n.content_type} if n else None,
                    "report_id": r.report_id})
    return out


class DecisionIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=1000)


@app.post("/api/review/{rid}/decide")
def review_decide(rid: int, body: DecisionIn, db: Session = Depends(get_session),
                  user: User = Depends(require_role("analyst"))):
    r = db.get(ReviewItem, rid)
    if not r or r.status != "pending":
        raise HTTPException(404, "gözləyən yoxlama elementi tapılmadı")
    if r.kind == "report" and user.role != "admin":
        raise HTTPException(403, "rəsmi hesabatın dərci yalnız admin təsdiqi ilə mümkündür")
    r.status = "approved" if body.approve else "rejected"
    r.reviewer_id, r.note, r.decided_at = user.id, body.note, datetime.now(timezone.utc)
    if r.kind == "risk" and r.news_id:
        a = db.get(NewsAnalysis, r.news_id)
        a.risk_status = "confirmed" if body.approve else "rejected"
        if not body.approve:
            a.risk_level = "low"
    elif r.kind in ("relevance", "low_confidence") and r.news_id:
        n = db.get(NewsItem, r.news_id)
        n.status = "relevant" if body.approve else "irrelevant"
        if body.approve and n.analysis and not n.analysis.category:
            from app.chains.news import classification_chain
            c = classification_chain().invoke({"title": n.title, "body": n.body, "content_type": n.content_type})
            n.analysis.category, n.analysis.location = c.category.category, c.category.location
            n.analysis.sentiment, n.analysis.sentiment_score = c.sentiment.sentiment, c.sentiment.score
            n.analysis.risk_level, n.analysis.risk_status = "low", "auto"
    elif r.kind == "report" and r.report_id:
        rep = db.get(Report, r.report_id)
        rep.status = "published" if body.approve else "rejected"
        rep.approved_by = user.id if body.approve else None
    db.add(AuditLog(user_id=user.id, action=f"review.{r.kind}.{r.status}", target=f"review:{r.id}", detail={"note": body.note}))
    for ns in ("dashboard", "latest_news", "search", "trends"):
        get_cache().invalidate(ns)
    return {"id": r.id, "status": r.status}


# ------------------------------------------------------------------ reports
@app.get("/api/reports")
def reports(db: Session = Depends(get_session), _: User = Depends(current_user)):
    rows = db.scalars(select(Report).order_by(Report.id.desc()).limit(50)).all()
    return [{"id": r.id, "title": r.title, "status": r.status, "created_at": r.created_at} for r in rows]


@app.get("/api/reports/{rid}")
def report_detail(rid: int, db: Session = Depends(get_session), _: User = Depends(current_user)):
    r = db.get(Report, rid)
    if not r:
        raise HTTPException(404, "hesabat tapılmadı")
    return {"id": r.id, "title": r.title, "body": r.body, "citations": r.citations, "status": r.status,
            "approved_by": r.approved_by, "created_at": r.created_at}


# ------------------------------------------------------------------ ingest (admin)
class NewsIn(BaseModel):
    source_name: str
    source_kind: Literal["official", "media", "social", "complaint"]
    title: str
    body: str
    published_at: datetime
    url: str | None = None


class DocIn(BaseModel):
    title: str
    source: str
    doc_type: Literal["official_news", "official_doc", "legislation", "media", "monitoring", "internal"]
    content: str = Field(min_length=20)
    published_at: datetime | None = None
    url: str | None = None
    approval_status: Literal["approved", "pending"] = "pending"
    access_roles: list[Literal["viewer", "analyst", "admin"]] = ["viewer", "analyst", "admin"]


@app.post("/api/ingest/news")
def ingest_news(items: list[NewsIn], db: Session = Depends(get_session), user: User = Depends(require_role("admin"))):
    st = process_batch(db, [RawNews(**i.model_dump()) for i in items])
    db.add(AuditLog(user_id=user.id, action="ingest.news", detail=st.as_dict()))
    return st.as_dict()


@app.post("/api/ingest/documents")
def ingest_docs(docs: list[DocIn], db: Session = Depends(get_session), user: User = Depends(require_role("admin"))):
    from langchain_core.documents import Document as LCDocument
    lc = [LCDocument(page_content=d.content, metadata={**d.model_dump(exclude={"content"}),
                                                       "published_at": d.published_at.isoformat() if d.published_at else None})
          for d in docs]
    st = ingest_documents(db, lc)
    db.add(AuditLog(user_id=user.id, action="ingest.documents", detail=st))
    get_cache().invalidate("search")
    return st


# ------------------------------------------------------------------ metrics
@app.get("/api/metrics")
def metrics(hours: int = Query(24, ge=1, le=720), db: Session = Depends(get_session),
            _: User = Depends(require_role("analyst"))):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    lat_rows = db.execute(select(RequestMetric.route, RequestMetric.latency_ms).where(RequestMetric.created_at >= since)).all()
    by_route: dict[str, list[float]] = defaultdict(list)
    for r, ms in lat_rows:
        by_route[r].append(ms)
    api = {r: {"count": len(v), "p50_ms": percentile(v, 0.5), "p95_ms": percentile(v, 0.95)} for r, v in by_route.items()}
    llm = db.execute(select(LLMCallLog.chain, func.count(), func.sum(LLMCallLog.input_tokens), func.sum(LLMCallLog.output_tokens),
                            func.sum(LLMCallLog.cost_usd), func.avg(LLMCallLog.latency_ms),
                            func.sum(case((LLMCallLog.status != "ok", 1), else_=0)))
                     .where(LLMCallLog.created_at >= since).group_by(LLMCallLog.chain)).all()
    tools = db.execute(select(ToolCallLog.tool, ToolCallLog.status, func.count(), func.avg(ToolCallLog.latency_ms))
                       .where(ToolCallLog.created_at >= since).group_by(ToolCallLog.tool, ToolCallLog.status)).all()
    tool_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"ok": 0, "failed": 0, "avg_ms": 0.0})
    for t, s, c, avg in tools:
        tool_stats[t]["ok" if s == "ok" else "failed"] += c
        tool_stats[t]["avg_ms"] = round(float(avg or 0), 1)
    for t in tool_stats.values():
        tot = t["ok"] + t["failed"]
        t["success_rate"] = round(t["ok"] / tot, 4) if tot else None
    runs = db.execute(select(CollectorRun.source, func.count(), func.avg(CollectorRun.max_ingest_lag_s),
                             func.avg(func.extract("epoch", CollectorRun.finished_at - CollectorRun.started_at)),
                             func.sum(CollectorRun.errors))
                      .where(CollectorRun.started_at >= since).group_by(CollectorRun.source)).all()
    return {
        "window_hours": hours,
        "cache": get_cache().info(),
        "api_latency": api,
        "llm": {c: {"calls": n, "input_tokens": int(i or 0), "output_tokens": int(o or 0), "cost_usd": round(float(cost or 0), 6),
                    "avg_latency_ms": round(float(lat or 0), 1), "error_rate": round((err or 0) / n, 4) if n else None}
                for c, n, i, o, cost, lat, err in llm},
        "tools": tool_stats,
        "collectors": [{"source": s, "runs": n, "avg_ingest_lag_s": round(float(lag or 0), 1),
                        "avg_run_s": round(float(rt or 0), 2), "errors": int(e or 0)} for s, n, lag, rt, e in runs],
        "review_queue": {k: v for k, v in db.execute(select(ReviewItem.kind, func.count()).where(
            ReviewItem.status == "pending").group_by(ReviewItem.kind)).all()},
        "llm_provider": provider_info(),
    }


@app.get("/api/prompts")
def prompts(_: User = Depends(current_user)):
    return [{"name": p.name, "version": p.version, "task": p.task, "schema": p.schema.__name__ if p.schema else None}
            for p in ALL_PROMPTS.values()]


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role,
            "tools": [t.name for t in TOOLS.values() if user.role in t.roles]}


# ------------------------------------------------------------------ frontend
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")
