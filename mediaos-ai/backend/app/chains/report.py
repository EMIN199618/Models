"""Chain 5 — Executive Report:
Verified News → Deduplication → Aggregation → Summary Chain → Report Output

Hesabat `pending_approval` statusunda yaranır; dərc üçün insan təsdiqi lazımdır.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any

from langchain_core.runnables import Runnable, RunnableLambda, RunnableParallel, RunnablePassthrough
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.chains.base import structured_step
from app.db import session_scope
from app.llm.prompts import registry as P
from app.llm.schemas import ExecutiveSummary
from app.models import NewsAnalysis, NewsItem
from app.text import hamming


def _load_verified(x: dict[str, Any]) -> dict[str, Any]:
    with session_scope() as db:
        rows = db.scalars(
            select(NewsItem).join(NewsAnalysis).options(joinedload(NewsItem.source), joinedload(NewsItem.analysis))
            .where(NewsItem.status == "relevant", NewsItem.published_at >= x["date_from"],
                   NewsItem.published_at <= x["date_to"])
            .order_by(NewsItem.published_at.desc())
        ).unique().all()
        items = [{
            "id": n.id, "title": n.title, "source": n.source.name, "simhash": n.simhash, "dup_of": n.dup_of_id,
            "date": n.published_at.isoformat(), "type": n.content_type, "category": n.analysis.category,
            "sentiment": n.analysis.sentiment, "risk": n.analysis.risk_level, "risk_status": n.analysis.risk_status,
            "verified": n.content_type == "official" or n.analysis.risk_status == "confirmed",
        } for n in rows]
    return {**x, "items": items}


def _dedupe(x: dict[str, Any]) -> dict[str, Any]:
    kept: list[dict[str, Any]] = []
    for it in x["items"]:
        if it["dup_of"]:
            continue
        twin = next((k for k in kept if hamming(k["simhash"], it["simhash"]) <= 6), None)
        if twin:
            twin["mentions"] = twin.get("mentions", 1) + 1
            continue
        kept.append(it)
    return {**x, "items": kept, "removed_duplicates": len(x["items"]) - len(kept)}


def _stats(x: dict[str, Any]) -> dict[str, Any]:
    items = x["items"]
    return {
        "total": len(items),
        "by_type": dict(Counter(i["type"] for i in items)),
        "by_sentiment": dict(Counter(i["sentiment"] for i in items)),
        "by_category": dict(Counter(i["category"] for i in items).most_common(5)),
        "risk_high": sum(i["risk"] == "high" for i in items),
        "risk_medium": sum(i["risk"] == "medium" for i in items),
        "removed_duplicates": x.get("removed_duplicates", 0),
    }


def _items_text(x: dict[str, Any]) -> str:
    order = {"official": 0, "media": 1, "public_opinion": 2}
    items = sorted(x["items"], key=lambda i: (order.get(i["type"], 3), {"high": 0, "medium": 1}.get(i["risk"], 2)))
    return "\n".join(
        f"[N{i['id']}] (type={i['type']}; category={i['category']}; sentiment={i['sentiment']}; risk={i['risk']}; "
        f"verified={'true' if i['verified'] else 'false'}; date={i['date'][:10]}) {i['title']}" for i in items[:60]
    )


def _render(x: dict[str, Any]) -> dict[str, Any]:
    s: ExecutiveSummary = x["summary"]
    valid = {f"N{i['id']}" for i in x["items"]}
    notes = []

    def clean(cites: list[str]) -> list[str]:
        bad = [c for c in cites if c not in valid]
        if bad:
            notes.append(f"etibarsız istinad silindi: {bad}")
        return [c for c in cites if c in valid]

    lines = [f"# DGK media monitorinqi — icmal", f"**Dövr:** {x['period']}", "", f"**{s.headline}**", "", "## Əsas məqamlar"]
    citations = set()
    for p in s.key_points:
        c = clean(p.citations)
        citations.update(c)
        lines.append(f"- {re.sub(r'\[N\d+\]', '', p.text).strip()} " + " ".join(f"[{i}]" for i in c))
    lines += ["", "## Risk siqnalları (insan təsdiqi tələb olunur)"]
    if s.risks:
        for p in s.risks:
            c = clean(p.citations)
            citations.update(c)
            lines.append(f"- {p.text} " + " ".join(f"[{i}]" for i in c))
    else:
        lines.append("- Dövr ərzində orta/yüksək risk siqnalı qeydə alınmayıb.")
    st = x["stats"]
    lines += ["", "## Statistika", f"- Cəmi: {st['total']} (dublikat çıxarıldı: {st['removed_duplicates']})",
              f"- Növ üzrə: {st['by_type']}", f"- Sentiment üzrə: {st['by_sentiment']}",
              f"- Əsas kateqoriyalar: {st['by_category']}"]
    if s.data_gaps:
        lines += ["", "## Məlumat çatışmazlıqları"] + [f"- {g}" for g in s.data_gaps]
    lines += ["", "_Qeyd: media və ictimai rəy materialları təsdiqlənmiş fakt deyil. Bu hesabat avtomatik hazırlanıb və dərcdən əvvəl insan təsdiqi tələb edir._"]
    by_id = {f"N{i['id']}": i for i in x["items"]}
    cites_out = [{"ref": c, "news_id": by_id[c]["id"], "title": by_id[c]["title"], "source": by_id[c]["source"],
                  "date": by_id[c]["date"], "type": by_id[c]["type"]} for c in sorted(citations, key=lambda c: int(c[1:]))]
    return {"title": f"DGK icmalı: {x['period']}", "body": "\n".join(lines), "citations": cites_out,
            "stats": st, "validation_notes": notes}


def report_chain() -> Runnable:
    summary = structured_step(P.EXEC_SUMMARY, "report", on_fail={"headline": "İcmal hazırlanmadı", "key_points": [],
                                                                "data_gaps": ["model cavabı alınmadı"]})
    return (
        RunnableLambda(_load_verified, name="load_verified_news")
        | RunnableLambda(_dedupe, name="deduplicate")
        | RunnablePassthrough.assign(**{"agg": RunnableParallel(stats=RunnableLambda(_stats), items_text=RunnableLambda(_items_text))})
        | RunnableLambda(lambda x: {**x, "stats": x["agg"]["stats"], "period": f"{x['date_from'].date()} — {x['date_to'].date()}"})
        | RunnablePassthrough.assign(summary=RunnableLambda(
            lambda x: {"period": x["period"], "stats": str(x["stats"]), "items": x["agg"]["items_text"]}) | summary)
        | RunnableLambda(_render, name="render_report")
    ).with_config(run_name="chain5_report")


def period_bounds(date_from: str | datetime, date_to: str | datetime) -> tuple[datetime, datetime]:
    from datetime import time, timezone
    df = date_from if isinstance(date_from, datetime) else datetime.combine(datetime.fromisoformat(date_from).date(), time.min, timezone.utc)
    dt = date_to if isinstance(date_to, datetime) else datetime.combine(datetime.fromisoformat(date_to).date(), time.max, timezone.utc)
    return df, dt
