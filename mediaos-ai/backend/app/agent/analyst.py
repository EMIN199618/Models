"""MEDIA OS AI Analyst — tool-calling agent.

Mesaj rolları dəqiq ayrılır:
  SystemMessage — agentin qaydaları + istifadəçinin təsdiqlənmiş uzunmüddətli yaddaşı
  HumanMessage  — istifadəçi sualları (qısamüddətli yaddaşdan əvvəlki suallar da)
  AIMessage     — model cavabları və tool_calls
  ToolMessage   — alət nəticələri (JSON); model bunları göstəriş kimi deyil, məlumat kimi alır
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.agent.tools import ToolContext, execute_tool, langchain_tools
from app.cache.redis_cache import get_cache, make_key
from app.config import get_settings
from app.llm.prompts.registry import AGENT
from app.llm.provider import get_tool_model, with_timeout
from app.memory import service as mem
from app.models import AuditLog, User
from app.observability.metrics import get_metrics_handler
from app.text import normalize_az

log = logging.getLogger(__name__)


def _trim_for_llm(result: dict[str, Any]) -> str:
    """Alət nəticəsini kontekst üçün qısaldır (uzun mətnlər, çoxlu element)."""
    r = dict(result)
    if isinstance(r.get("items"), list):
        r["items"] = r["items"][:12]
    if "report" in r:
        r["report"] = {**r["report"], "body": r["report"]["body"][:4000]}
    r.pop("citations", None) if "report" in r else None
    return json.dumps(r, ensure_ascii=False, default=str)[:12000]


def run_agent(db: Session, user: User, question: str, conversation_id: str | None = None,
              today: date | None = None) -> dict[str, Any]:
    s = get_settings()
    t0 = time.perf_counter()
    today = today or date.today()
    conv = mem.get_or_create_conversation(db, user.id, conversation_id)
    history = mem.load_history(db, user.id, conv)
    user_memory = mem.memory_context(db, user.id)

    # Keş: yalnız söhbətin ilk sualı (kontekstdən asılı olmayan) və yalnız bu istifadəçi üçün
    cache = get_cache()
    cache_key = make_key(normalize_az(question), user_memory, user.role, today.isoformat())
    if not history:
        hit = cache.get("ai_answer", cache_key, scope=f"user:{user.id}")
        if hit:
            mem.append_turn(db, user.id, conv, question, hit["answer"], {"cached": True})
            return {**hit, "conversation_id": str(conv.id), "cached": True,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}

    ctx = ToolContext(user_id=user.id, role=user.role, conversation_id=conv.id)
    tools = langchain_tools(user.role)
    model = with_timeout(get_tool_model(tools)).with_config(
        metadata={"chain": "agent", "prompt_name": AGENT.name, "prompt_version": AGENT.version},
        callbacks=[get_metrics_handler()])
    messages: list[BaseMessage] = AGENT.template().invoke(
        {"input": question, "history": history, "user_memory": user_memory, "today": today.isoformat()}
    ).to_messages()

    trace: list[dict[str, Any]] = []
    answer = ""
    for _step in range(s.agent_max_steps):
        ai: AIMessage = model.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            answer = str(ai.content)
            break
        for call in ai.tool_calls:
            res = execute_tool(ctx, call["name"], call["args"])
            trace.append({"tool": call["name"], "args": call["args"], "status": res.get("status")})
            messages.append(ToolMessage(content=_trim_for_llm(res), tool_call_id=call["id"], name=call["name"]))
    else:
        answer = "Analiz addım limiti aşıldı; sualı dəqiqləşdirin."

    # Mənbə yoxlaması: cavabdakı istinadlar alətlərin qaytardığı mənbələr arasında olmalıdır
    cited = list(dict.fromkeys(re.findall(r"\[([NSE]\d+)\]", answer)))
    bogus = [c for c in cited if c not in ctx.refs]
    for b in bogus:
        answer = answer.replace(f"[{b}]", "[mənbə təsdiqlənmədi]")
    citations = [ctx.refs[c] for c in cited if c in ctx.refs]
    used_tools = {t["tool"] for t in trace}
    out = {
        "answer": answer,
        "citations": [{k: v for k, v in c.items() if k in ("ref", "title", "source", "date", "content_type", "doc_type", "url")}
                      for c in citations],
        "tools": trace,
        "uses": {"rag": bool(used_tools & {"semantic_search", "search_official_sources", "compare_news"}),
                 "memory": {"short_term_messages": len(history), "long_term": user_memory != "(yoxdur)"},
                 "tool_calling": bool(trace)},
        "validation": {"removed_citations": bogus},
    }
    mem.append_turn(db, user.id, conv, question, answer, {"tools": trace, "citations": cited})
    db.add(AuditLog(user_id=user.id, action="agent.chat", target=f"conversation:{conv.id}",
                    detail={"question": question[:300], "tools": trace, "citations": cited}))
    if not history and trace and all(t["status"] == "ok" for t in trace) and "generate_report" not in used_tools:
        cache.set("ai_answer", cache_key, out, s.cache_ttl_ai_answer, scope=f"user:{user.id}")
    return {**out, "conversation_id": str(conv.id), "cached": False,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
