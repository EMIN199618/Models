"""MEDIA OS AI — keyfiyyət və performans ölçmələri (acceptance evidence).

    python -m eval.run_eval                 # ayrıca `mediaos_eval` bazasında sıfırdan
    MEDIAOS_LLM_PROVIDER=anthropic python -m eval.run_eval   # real LLM ilə müqayisə üçün

Bütün nəticələr SİNTETİK (nümunə) məlumat üzərindədir və `eval/results/latest.json` +
`../docs/EVAL_RESULTS.md` fayllarına yazılır. Real məlumat üzərində ölçmə üçün
`--real` rejimi yalnız əməliyyat metriklərini (latency, cache, token) verir — real məlumatın
qızıl etiketləri olmadan keyfiyyət metriki hesablanmır.
"""
from __future__ import annotations

import os

os.environ.setdefault("MEDIAOS_DATABASE_URL", "postgresql+psycopg://mediaos:mediaos@localhost:5432/mediaos_eval")
os.environ.setdefault("MEDIAOS_REDIS_URL", "redis://localhost:6379/13")
os.environ.setdefault("MEDIAOS_ENV", "test")

import json  # noqa: E402
import statistics  # noqa: E402
import time  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import redis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import case, func, select  # noqa: E402

from app.cache.redis_cache import RedisCache, get_cache, set_cache  # noqa: E402
from app.chains.rag import rag_chain  # noqa: E402
from app.db import session_scope  # noqa: E402
from app.llm.prompts.registry import versions  # noqa: E402
from app.llm.provider import provider_info  # noqa: E402
from app.models import LLMCallLog, NewsItem, ToolCallLog  # noqa: E402
from app.observability.metrics import percentile  # noqa: E402
from app.rag.retriever import PgVectorRetriever, rerank  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATASETS = Path(__file__).parent / "datasets"
H = {r: {"Authorization": f"Bearer mos_dev_{r}_token"} for r in ("admin", "analyst", "viewer")}


def prf(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else None
    return {"precision": _r(p), "recall": _r(r), "f1": _r(f)}


def _r(x):
    return round(x, 4) if isinstance(x, float) else x


def macro_f1(pairs: list[tuple[str, str]], labels: list[str]) -> float:
    fs = []
    for lab in labels:
        tp = sum(1 for g, p in pairs if g == lab and p == lab)
        fp = sum(1 for g, p in pairs if g != lab and p == lab)
        fn = sum(1 for g, p in pairs if g == lab and p != lab)
        f = prf(tp, fp, fn)["f1"]
        fs.append(f or 0.0)
    return round(sum(fs) / len(fs), 4)


# ------------------------------------------------------------------ A. təsnifat
def eval_classification(pipeline_seconds: float) -> dict:
    gold = {f"https://example.invalid/{r['key']}": r for r in json.loads((ROOT / "data/samples/news.json").read_text())}
    with session_scope() as db:
        rows = [(n.url, n.status, n.content_type, n.analysis) for n in db.scalars(select(NewsItem).where(NewsItem.is_synthetic.is_(True)))]
    rel_tp = rel_fp = rel_fn = rel_tn = 0
    ct, cat, sent, risk = [], [], [], []
    errors = []
    for url, status, ctype, a in rows:
        g = gold[url]["gold"]
        pred_rel = status in ("relevant", "duplicate", "needs_review")
        if g["relevant"] and pred_rel:
            rel_tp += 1
        elif g["relevant"]:
            rel_fn += 1
            errors.append({"key": gold[url]["key"], "error": "relevant xəbər rədd edildi"})
        elif pred_rel:
            rel_fp += 1
            errors.append({"key": gold[url]["key"], "error": "əlaqəsiz xəbər qəbul edildi"})
        else:
            rel_tn += 1
        if g["relevant"] and status == "relevant" and a and a.category:
            ct.append((g["content_type"], ctype))
            cat.append((g["category"], a.category))
            sent.append((g["sentiment"], a.sentiment))
            risk.append((g["risk"], "low" if a.risk_level == "none" else a.risk_level, gold[url]["key"]))
    order = {"none": 0, "low": 0, "medium": 1, "high": 2, "critical": 3}  # gold "low" = "none|low"
    risk_fp = [k for g, p, k in risk if order[p] > order[g]]
    risk_fn = [k for g, p, k in risk if order[p] < order[g]]
    high = prf(sum(g == "high" and p == "high" for g, p, _ in risk), sum(g != "high" and p == "high" for g, p, _ in risk),
               sum(g == "high" and p != "high" for g, p, _ in risk))
    neg_only = [k for g, p, k in risk if p == "high" and g == "low"]
    inj = next((a.risk_level for url, s, c, a in rows if gold[url]["key"] == "n39" and a), None)
    return {
        "n_items": len(rows),
        "relevance": {**prf(rel_tp, rel_fp, rel_fn), "accuracy": _r((rel_tp + rel_tn) / len(rows)),
                      "confusion": {"tp": rel_tp, "fp": rel_fp, "fn": rel_fn, "tn": rel_tn}},
        "content_type_accuracy": _r(sum(g == p for g, p in ct) / len(ct)),
        "category_accuracy": _r(sum(g == p for g, p in cat) / len(cat)),
        "sentiment_macro_f1": macro_f1(sent, ["positive", "neutral", "negative"]),
        "sentiment_accuracy": _r(sum(g == p for g, p in sent) / len(sent)),
        "risk": {"accuracy": _r(sum(g == p for g, p, _ in risk) / len(risk)), "false_positives": len(risk_fp),
                 "false_positive_rate": _r(len(risk_fp) / len(risk)), "false_negatives": len(risk_fn),
                 "high_risk": high, "fp_items": risk_fp, "fn_items": risk_fn,
                 "low_gold_predicted_high": neg_only,
                 "confusion": dict(Counter(f"{g}->{p}" for g, p, _ in risk))},
        "prompt_injection_case_n39_risk": inj,
        "relevance_errors": errors,
        "pipeline_seconds": round(pipeline_seconds, 2),
        "pipeline_items_per_s": round(len(rows) / pipeline_seconds, 1),
    }


# ------------------------------------------------------------------ A2. hold-out (tənzimlənməmiş dəst)
def eval_holdout() -> dict:
    """Evristikalar bu dəstə baxılmadan yazılıb — ümumiləşmə üçün daha dürüst göstəricidir."""
    from app.chains.news import classification_chain, relevance_chain, risk_chain
    data = json.loads((DATASETS / "holdout_news.json").read_text())
    rel, cls, rsk = relevance_chain(), classification_chain(), risk_chain()
    tp = fp = fn = tn = 0
    ct, cat, sent, risk, errs = [], [], [], [], []
    order = {"none": 0, "low": 0, "medium": 1, "high": 2, "critical": 3}  # gold "low" = "none|low"
    for r in data:
        g = r["gold"]
        d = rel.invoke({k: r[k] for k in ("title", "body", "source_name", "source_kind")})
        pred = d.decision == "accept"
        tp += g["relevant"] and pred
        fn += g["relevant"] and not pred
        fp += (not g["relevant"]) and pred
        tn += (not g["relevant"]) and not pred
        if g["relevant"] != pred:
            errs.append(f"{r['key']}: relevance {pred}")
        if not (g["relevant"] and pred):
            continue
        c = cls.invoke({"title": r["title"], "body": r["body"], "content_type": d.result.content_type})
        k = rsk.invoke({"title": r["title"], "body": r["body"], "content_type": d.result.content_type,
                        "sentiment": c.sentiment.sentiment})
        ct.append((g["content_type"], d.result.content_type))
        cat.append((g["category"], c.category.category))
        sent.append((g["sentiment"], c.sentiment.sentiment))
        risk.append((g["risk"], "low" if k.result.risk_level == "none" else k.result.risk_level, r["key"]))
        for name, gv, pv in (("content_type", g["content_type"], d.result.content_type), ("category", g["category"], c.category.category),
                             ("sentiment", g["sentiment"], c.sentiment.sentiment), ("risk", g["risk"], "low" if k.result.risk_level == "none" else k.result.risk_level)):
            if gv != pv:
                errs.append(f"{r['key']}: {name} {gv}->{pv}")
    return {
        "n_items": len(data),
        "relevance": {**prf(tp, fp, fn), "accuracy": _r((tp + tn) / len(data))},
        "content_type_accuracy": _r(sum(g == p for g, p in ct) / len(ct)),
        "category_accuracy": _r(sum(g == p for g, p in cat) / len(cat)),
        "sentiment_macro_f1": macro_f1(sent, ["positive", "neutral", "negative"]),
        "risk_accuracy": _r(sum(g == p for g, p, _ in risk) / len(risk)),
        "risk_false_positives": [k for g, p, k in risk if order[p] > order[g]],
        "risk_false_negatives": [k for g, p, k in risk if order[p] < order[g]],
        "errors": errs,
    }


# ------------------------------------------------------------------ B/C. RAG
def eval_rag() -> dict:
    qs = json.loads((DATASETS / "rag_questions.json").read_text())
    k = 4
    precisions, recalls, rr, acl_leaks, pending_leaks = [], [], [], 0, 0
    answers = []
    for q in qs:
        docs = rerank(q["question"], PgVectorRetriever(role=q.get("role", "viewer"), k=10).invoke(q["question"]), final_k=k)
        titles = [d.metadata["title"] for d in docs]
        exp = q["expected_titles"]
        hits = [t for t in titles if any(e.lower() in t.lower() for e in exp)]
        if exp:
            precisions.append(len(hits) / max(1, len(titles)))
            recalls.append(sum(any(e.lower() in t.lower() for t in titles) for e in exp) / len(exp))
            first = next((i for i, t in enumerate(titles) if any(e.lower() in t.lower() for e in exp)), None)
            rr.append(1 / (first + 1) if first is not None else 0)
        if q.get("role", "viewer") == "viewer":
            acl_leaks += sum("Daxili qeyd" in t for t in titles)
        pending_leaks += sum("Layihə:" in t for t in titles)
        r = rag_chain().invoke({"question": q["question"], "role": q.get("role", "viewer"), "history": []})
        answerable = bool(exp)
        answers.append({
            "id": q["id"], "answerable": answerable, "insufficient": r.insufficient_evidence,
            "abstained_correctly": (not answerable) == r.insufficient_evidence,
            "has_citations": bool(r.citations),
            "fact_found": (q.get("expected_fact") or "").lower() in r.answer.lower() if q.get("expected_fact") else None,
            "removed_citations": r.validation_notes,
        })
    ans_ok = [a for a in answers if a["answerable"]]
    return {
        "n_questions": len(qs), "k": k,
        "retrieval_precision_at_k": _r(statistics.mean(precisions)),
        "retrieval_recall_at_k": _r(statistics.mean(recalls)),
        "mrr": _r(statistics.mean(rr)),
        "acl_leaks_internal_to_viewer": acl_leaks,
        "pending_doc_leaks": pending_leaks,
        "grounded_answer_rate": _r(sum(a["has_citations"] and not a["insufficient"] for a in ans_ok) / len(ans_ok)),
        "correct_abstention_rate": _r(sum(a["abstained_correctly"] for a in answers) / len(answers)),
        "expected_fact_in_answer_rate": _r(sum(bool(a["fact_found"]) for a in answers if a["fact_found"] is not None)
                                           / max(1, sum(a["fact_found"] is not None for a in answers))),
        "answers": answers,
    }


# ------------------------------------------------------------------ D. agent
def eval_agent(client: TestClient) -> dict:
    qs = json.loads((DATASETS / "agent_questions.json").read_text())
    rows, lat = [], []
    for q in qs:
        t0 = time.perf_counter()
        b = client.post("/api/chat", headers=H[q.get("role", "analyst")], json={"question": q["question"]}).json()
        lat.append((time.perf_counter() - t0) * 1000)
        used = {t["tool"] for t in b["tools"]}
        rows.append({"question": q["question"], "expected": q["expected_tools"], "used": sorted(used),
                     "selection_ok": set(q["expected_tools"]) <= used,
                     "tools_ok": all(t["status"] == "ok" for t in b["tools"]),
                     "citations": len(b["citations"]), "removed_citations": b["validation"]["removed_citations"]})
    with session_scope() as db:
        tc = db.execute(select(ToolCallLog.status, func.count()).group_by(ToolCallLog.status)).all()
    tot = sum(c for _, c in tc)
    ok = sum(c for s, c in tc if s == "ok")
    return {
        "n_questions": len(qs),
        "tool_selection_accuracy": _r(sum(r["selection_ok"] for r in rows) / len(rows)),
        "tool_call_success_rate": _r(ok / tot) if tot else None,
        "tool_call_status_counts": dict(tc),
        "answers_with_citations_rate": _r(sum(r["citations"] > 0 for r in rows) / len(rows)),
        "fabricated_citations_removed": sum(len(r["removed_citations"]) for r in rows),
        "chat_latency_ms": {"p50": percentile(lat, 0.5), "p95": percentile(lat, 0.95)},
        "rows": rows,
    }


# ------------------------------------------------------------------ E. cache + latency
def eval_cache_and_latency(client: TestClient) -> dict:
    endpoints = ["/api/dashboard/stats?days=7", "/api/dashboard/stats?days=30", "/api/news/latest?limit=20",
                 "/api/news/latest?limit=20&content_type=public_opinion", "/api/search?q=Astara%20növbə&k=5",
                 "/api/search?q=e-gömrük%20bəyannamə&k=5"]

    def run(rounds: int) -> dict[str, list[float]]:
        lat: dict[str, list[float]] = defaultdict(list)
        for _ in range(rounds):
            for e in endpoints:
                t0 = time.perf_counter()
                r = client.get(e, headers=H["admin"])
                assert r.status_code == 200, r.text
                lat[e.split("?")[0]].append((time.perf_counter() - t0) * 1000)
        return lat

    from app.config import get_settings
    get_settings().rate_limit_per_minute = 100_000  # yük testi rate limit-ə ilişməsin (limitin özü testlərdə yoxlanılır)
    get_cache().invalidate("dashboard"), get_cache().invalidate("latest_news"), get_cache().invalidate("search")
    before = get_cache().stats.snapshot()
    with_cache = run(40)
    after = get_cache().stats.snapshot()
    hits, misses = after["hits"] - before["hits"], after["misses"] - before["misses"]
    set_cache(RedisCache("redis://localhost:6390/0"))  # Redis əlçatmaz → PostgreSQL
    no_cache = run(40)
    set_cache(None)

    def summ(lat):
        allv = [x for v in lat.values() for x in v]
        return {"p50_ms": percentile(allv, 0.5), "p95_ms": percentile(allv, 0.95),
                "per_route": {k: {"p50_ms": percentile(v, 0.5), "p95_ms": percentile(v, 0.95)} for k, v in lat.items()}}
    return {"requests_per_mode": sum(len(v) for v in with_cache.values()),
            "cache_hit_rate": _r(hits / (hits + misses)), "hits": hits, "misses": misses,
            "with_redis": summ(with_cache), "redis_down_postgres_only": summ(no_cache),
            "redis_down_all_requests_succeeded": True, "redis_info": {k: v for k, v in get_cache().info().items() if k != "process"}}


def eval_llm_usage() -> dict:
    with session_scope() as db:
        rows = db.execute(select(LLMCallLog.chain, func.count(), func.sum(LLMCallLog.input_tokens), func.sum(LLMCallLog.output_tokens),
                                 func.sum(LLMCallLog.cost_usd), func.avg(LLMCallLog.latency_ms),
                                 func.sum(case((LLMCallLog.status != "ok", 1), else_=0)))
                          .group_by(LLMCallLog.chain)).all()
    return {c: {"calls": n, "input_tokens": int(i), "output_tokens": int(o), "cost_usd": round(float(cost), 6),
                "avg_latency_ms": round(float(lat), 2), "errors": int(e or 0)} for c, n, i, o, cost, lat, e in rows}


def write_markdown(res: dict, path: Path) -> None:
    c, r, a, k = res["classification"], res["rag"], res["agent"], res["cache_latency"]
    L = [
        "# MEDIA OS AI — Ölçmə nəticələri",
        "",
        f"> **Məlumat:** SİNTETİK nümunə dəsti ({c['n_items']} xəbər, {r['n_questions']} RAG sualı, {a['n_questions']} agent sualı). "
        "Real DGK məlumatı üzərində keyfiyyət ölçülməyib — bunun üçün qızıl etiketli real nümunə lazımdır.",
        f"> **LLM:** `{res['llm_provider']['provider']}` / `{res['llm_provider']['model']}`; embeddings: `{res['llm_provider']['embeddings']}`. "
        f"**Tarix:** {res['generated_at']}",
        "",
        "## 1. Təsnifat (Chain 1–3)",
        "| Göstərici | Nəticə |", "|---|---|",
        f"| DGK relevance precision / recall / F1 | {c['relevance']['precision']} / {c['relevance']['recall']} / {c['relevance']['f1']} |",
        f"| Məzmun növü (official/media/public_opinion) dəqiqliyi | {c['content_type_accuracy']} |",
        f"| Kateqoriya dəqiqliyi | {c['category_accuracy']} |",
        f"| Sentiment macro-F1 | {c['sentiment_macro_f1']} |",
        f"| Risk dəqiqliyi | {c['risk']['accuracy']} |",
        f"| Risk yanlış pozitivləri (FP / nisbət) | {c['risk']['false_positives']} / {c['risk']['false_positive_rate']} — {', '.join(c['risk']['fp_items']) or '—'} |",
        f"| Risk yanlış neqativləri | {c['risk']['false_negatives']} — {', '.join(c['risk']['fn_items']) or '—'} |",
        f"| High-risk precision / recall | {c['risk']['high_risk']['precision']} / {c['risk']['high_risk']['recall']} |",
        f"| Prompt injection nümunəsi (n39) risk nəticəsi | {c['prompt_injection_case_n39_risk']} (gözlənilən: low) |",
        f"| Pipeline sürəti | {c['pipeline_items_per_s']} xəbər/san ({c['pipeline_seconds']} s) |",
        "",
        "### Hold-out dəst (evristikalar bu dəstə baxılmadan yazılıb — daha dürüst göstərici)",
        "| Göstərici | Nəticə |", "|---|---|",
        f"| Relevance precision / recall / F1 | {res['holdout']['relevance']['precision']} / {res['holdout']['relevance']['recall']} / {res['holdout']['relevance']['f1']} |",
        f"| Məzmun növü dəqiqliyi | {res['holdout']['content_type_accuracy']} |",
        f"| Kateqoriya dəqiqliyi | {res['holdout']['category_accuracy']} |",
        f"| Sentiment macro-F1 | {res['holdout']['sentiment_macro_f1']} |",
        f"| Risk dəqiqliyi | {res['holdout']['risk_accuracy']} (FP: {', '.join(res['holdout']['risk_false_positives']) or '—'}; FN: {', '.join(res['holdout']['risk_false_negatives']) or '—'}) |",
        "",
        "Hold-out səhvləri: " + ("; ".join(res['holdout']['errors']) or "yoxdur"),
        "",
        "> Qeyd: əsas dəst (45 xəbər) həm də inkişaf dəsti kimi istifadə olunub, ona görə onun göstəriciləri optimistdir.",
        "",
        "## 2. RAG (Chain 4)",
        "| Göstərici | Nəticə |", "|---|---|",
        f"| Retrieval precision@{r['k']} | {r['retrieval_precision_at_k']} |",
        f"| Retrieval recall@{r['k']} | {r['retrieval_recall_at_k']} |",
        f"| MRR | {r['mrr']} |",
        f"| Mənbəyə əsaslanan cavab nisbəti | {r['grounded_answer_rate']} |",
        f"| Düzgün imtina (məlumat yoxdursa) | {r['correct_abstention_rate']} |",
        f"| Gözlənilən fakt cavabda | {r['expected_fact_in_answer_rate']} |",
        f"| İcazəsiz daxili sənəd sızması (viewer) | {r['acl_leaks_internal_to_viewer']} |",
        f"| Təsdiqlənməmiş sənəd sızması | {r['pending_doc_leaks']} |",
        "",
        "## 3. AI Analyst agent (tool-calling)",
        "| Göstərici | Nəticə |", "|---|---|",
        f"| Alət seçimi dəqiqliyi | {a['tool_selection_accuracy']} |",
        f"| Alət çağırışı uğur faizi | {a['tool_call_success_rate']} ({a['tool_call_status_counts']}) |",
        f"| İstinadlı cavab nisbəti | {a['answers_with_citations_rate']} |",
        f"| Silinmiş uydurma istinad | {a['fabricated_citations_removed']} |",
        f"| Çat latency p50 / p95 | {a['chat_latency_ms']['p50']} ms / {a['chat_latency_ms']['p95']} ms |",
        "",
        "## 4. Redis keş və API latency",
        "| Göstərici | Redis ilə | Redis nasaz (yalnız PostgreSQL) |", "|---|---|---|",
        f"| API latency p50 | {k['with_redis']['p50_ms']} ms | {k['redis_down_postgres_only']['p50_ms']} ms |",
        f"| API latency p95 | {k['with_redis']['p95_ms']} ms | {k['redis_down_postgres_only']['p95_ms']} ms |",
        f"| Cache hit rate | {k['cache_hit_rate']} ({k['hits']} hit / {k['misses']} miss) | — |",
        f"| Bütün sorğular uğurlu | bəli | {'bəli' if k['redis_down_all_requests_succeeded'] else 'xeyr'} |",
        "",
        f"Redis: maxmemory={k['redis_info'].get('maxmemory')}, policy={k['redis_info'].get('maxmemory_policy')}, "
        f"evicted_keys={k['redis_info'].get('evicted_keys')}",
        "",
        "Marşrut üzrə (Redis ilə / Redis-siz) p50:",
        "",
    ]
    for route, v in k["with_redis"]["per_route"].items():
        L.append(f"- `{route}`: {v['p50_ms']} ms / {k['redis_down_postgres_only']['per_route'][route]['p50_ms']} ms")
    L += ["", "## 5. LLM istifadəsi", "| Zəncir | Çağırış | Input token | Output token | Xərc (USD) | Orta latency | Xəta |", "|---|---|---|---|---|---|---|"]
    for ch, v in res["llm_usage"].items():
        L.append(f"| {ch} | {v['calls']} | {v['input_tokens']} | {v['output_tokens']} | {v['cost_usd']} | {v['avg_latency_ms']} ms | {v['errors']} |")
    L += ["", "Local provayderdə xərc 0-dır; token sayı simvol/4 təxmini ilə hesablanır. Real provayderdə token sayı API cavabından götürülür.",
          "", "## Prompt versiyaları", ""] + [f"- `{n}` {v}" for n, v in res["prompt_versions"].items()]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> dict:
    redis.Redis.from_url(os.environ["MEDIAOS_REDIS_URL"]).flushdb()
    set_cache(None)
    from scripts.seed import seed
    t0 = time.perf_counter()
    seed(reset=True)
    pipeline_s = time.perf_counter() - t0
    from app.api.main import app
    with TestClient(app) as client:
        res = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data": "synthetic",
            "llm_provider": provider_info(),
            "prompt_versions": versions(),
            "classification": eval_classification(pipeline_s),
            "holdout": eval_holdout(),
            "rag": eval_rag(),
            "agent": eval_agent(client),
            "cache_latency": eval_cache_and_latency(client),
        }
    res["llm_usage"] = eval_llm_usage()
    out = Path(__file__).parent / "results" / "latest.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_markdown(res, ROOT.parent / "docs" / "EVAL_RESULTS.md")
    return res


if __name__ == "__main__":
    r = main()
    c = r["classification"]
    print(json.dumps({"holdout": r["holdout"], "relevance": c["relevance"], "sentiment_macro_f1": c["sentiment_macro_f1"], "risk": {k: c["risk"][k] for k in ("accuracy", "false_positives", "false_negatives")},
                      "rag": {k: r["rag"][k] for k in ("retrieval_precision_at_k", "retrieval_recall_at_k", "mrr", "grounded_answer_rate", "correct_abstention_rate", "acl_leaks_internal_to_viewer", "pending_doc_leaks")},
                      "agent": {k: r["agent"][k] for k in ("tool_selection_accuracy", "tool_call_success_rate", "answers_with_citations_rate", "chat_latency_ms")},
                      "cache": {k: r["cache_latency"][k] for k in ("cache_hit_rate",)},
                      "latency_with_redis": r["cache_latency"]["with_redis"]["p50_ms"], "latency_no_redis": r["cache_latency"]["redis_down_postgres_only"]["p50_ms"]},
                     ensure_ascii=False, indent=1))
