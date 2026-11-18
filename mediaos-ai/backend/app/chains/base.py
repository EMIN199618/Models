"""LCEL ümumi tikinti blokları."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, ValidationError

from app.llm.prompts.registry import PromptSpec
from app.llm.provider import get_chat_model, with_timeout
from app.observability.metrics import get_metrics_handler

log = logging.getLogger(__name__)
RECOVERABLE = (OutputParserException, ValidationError, TimeoutError, ValueError, RuntimeError)


def structured_step(spec: PromptSpec, chain_name: str, on_fail: dict[str, Any] | None = None) -> Runnable:
    """ChatPromptTemplate → ChatModel (retry+fallback+timeout) → PydanticOutputParser.

    Uğursuzluqda (parse xətası, timeout, provayder xətası) `on_fail` dəyəri ilə
    confidence=0 olan nəticə qaytarılır — belə nəticə
    avtomatik insan yoxlamasına gedir. Uydurma cavab yaradılmır.
    """
    assert spec.parser is not None
    core = (spec.template() | with_timeout(get_chat_model()) | spec.parser).with_config(
        run_name=f"{chain_name}:{spec.ref}",
        metadata={"chain": chain_name, "prompt_name": spec.name, "prompt_version": spec.version},
        callbacks=[get_metrics_handler()],
    )

    def _fail(x: dict[str, Any]) -> BaseModel:
        log.warning("%s uğursuz oldu, insan yoxlamasına göndərilir", spec.ref)
        assert spec.schema is not None
        return spec.schema.model_validate({**(on_fail or {}), "confidence": 0.0})

    if on_fail is None:
        return core
    return core.with_fallbacks([RunnableLambda(_fail, name="safe_default")], exceptions_to_handle=RECOVERABLE)
