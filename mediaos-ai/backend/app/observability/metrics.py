"""LLM müşahidəsi: token, latency, xəta faizi, təxmini xərc.

`LLMMetricsHandler` LangChain callback-dir; hər chat model çağırışında avtomatik işləyir
və nəticəni `llm_calls` cədvəlinə yazır. Zəncir adı və prompt versiyası `config.metadata`-dan gəlir.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.config import get_settings

log = logging.getLogger(__name__)


class LLMMetricsHandler(BaseCallbackHandler):
    raise_error = False

    def __init__(self, persist: bool = True):
        self.persist = persist
        self._starts: dict[UUID, tuple[float, dict[str, Any], str]] = {}
        self._lock = threading.Lock()
        self.totals: dict[str, Any] = defaultdict(float)

    def on_chat_model_start(self, serialized, messages, *, run_id: UUID, metadata=None, **kwargs):
        name = (serialized or {}).get("name") or (serialized or {}).get("id", ["?"])[-1]
        with self._lock:
            self._starts[run_id] = (time.perf_counter(), dict(metadata or {}), str(name))

    def _finish(self, run_id: UUID, status: str, in_tok: int, out_tok: int, model: str, error: str | None):
        with self._lock:
            start, meta, cls = self._starts.pop(run_id, (time.perf_counter(), {}, "?"))
        latency = (time.perf_counter() - start) * 1000
        s = get_settings()
        cost = in_tok / 1e6 * s.llm_cost_input_per_mtok + out_tok / 1e6 * s.llm_cost_output_per_mtok
        if "local" in cls.lower() or "ollama" in cls.lower() or model.startswith("local"):  # lokal model: API xərci yoxdur
            cost = 0.0
        with self._lock:
            self.totals["calls"] += 1
            self.totals["errors"] += status != "ok"
            self.totals["input_tokens"] += in_tok
            self.totals["output_tokens"] += out_tok
            self.totals["cost_usd"] += cost
        if not self.persist:
            return
        try:
            from app.db import session_scope
            from app.models import LLMCallLog
            with session_scope() as db:
                db.add(LLMCallLog(
                    chain=str(meta.get("chain", "unknown")), prompt_name=str(meta.get("prompt_name", "")),
                    prompt_version=str(meta.get("prompt_version", "")), provider=cls, model=model or cls,
                    input_tokens=in_tok, output_tokens=out_tok, latency_ms=latency, cost_usd=cost,
                    status=status, error=error,
                ))
        except Exception as exc:  # müşahidə heç vaxt əsas axını sındırmamalıdır
            log.debug("llm metric yazılmadı: %s", exc)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs):
        in_tok = out_tok = 0
        model = ""
        try:
            msg = response.generations[0][0].message  # type: ignore[attr-defined]
            um = getattr(msg, "usage_metadata", None) or {}
            in_tok, out_tok = int(um.get("input_tokens", 0)), int(um.get("output_tokens", 0))
            model = (msg.response_metadata or {}).get("model_name") or (msg.response_metadata or {}).get("model", "")
        except Exception:
            pass
        self._finish(run_id, "ok", in_tok, out_tok, model, None)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs):
        self._finish(run_id, "error", 0, 0, "", str(error)[:500])


_handler: LLMMetricsHandler | None = None


def get_metrics_handler() -> LLMMetricsHandler:
    global _handler
    if _handler is None:
        _handler = LLMMetricsHandler()
    return _handler


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    k = (len(v) - 1) * p
    f, c = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[f] + (v[c] - v[f]) * (k - f), 2)
