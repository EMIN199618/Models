"""LLM xidmət qatı: provayder seçimi konfiqurasiya ilə, retry, timeout, fallback.

    MEDIAOS_LLM_PROVIDER=anthropic MEDIAOS_LLM_MODEL=claude-sonnet-5-5   → Claude
    MEDIAOS_LLM_PROVIDER=openai    MEDIAOS_LLM_MODEL=gpt-...             → OpenAI
    MEDIAOS_LLM_PROVIDER=local                                           → oflayn model

Real provayder xəta verəndə (retry-lardan sonra) zəncir `local` modelə keçir və nəticə
aşağı etibarlılıq kimi işarələnə bilər.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from app.config import get_settings
from app.llm.local_model import LocalAnalystModel

_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="llm-timeout")


def _ollama(json_mode: bool) -> BaseChatModel:
    from langchain_ollama import ChatOllama
    s = get_settings()
    # json_mode: strukturlaşdırılmış cavablar (Pydantic sxemi) üçün Ollama-nın JSON rejimi.
    # Tool-calling zamanı JSON rejimi qoyulmur — model tool_calls qaytarmalıdır.
    return ChatOllama(model=s.ollama_model, base_url=s.ollama_base_url, temperature=0, num_ctx=s.ollama_num_ctx,
                      keep_alive=s.ollama_keep_alive, format="json" if json_mode else None,
                      client_kwargs={"timeout": s.ollama_timeout_s})


def _primary(json_mode: bool = True) -> BaseChatModel:
    s = get_settings()
    if s.llm_provider == "ollama":
        return _ollama(json_mode)
    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        # temperature göndərilmir: Claude Opus 5.5 sampling parametrlərini qəbul etmir (400).
        # API açarı ANTHROPIC_API_KEY mühit dəyişənindən oxunur.
        return ChatAnthropic(model=s.llm_model, base_url=s.anthropic_base_url, timeout=s.llm_timeout_s,
                             max_retries=0, max_tokens=s.llm_max_tokens)
    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=s.llm_model, temperature=s.llm_temperature, timeout=s.llm_timeout_s, max_retries=0)
    return LocalAnalystModel()


def _wrap(primary: Runnable, fallback: Runnable | None) -> Runnable:
    s = get_settings()
    r: Runnable = primary.with_retry(stop_after_attempt=s.llm_max_retries + 1, wait_exponential_jitter=True)
    if fallback is not None:
        r = r.with_fallbacks([fallback])
    return r


def get_chat_model() -> Runnable:
    s = get_settings()
    primary = _primary()
    fb = LocalAnalystModel() if (s.llm_fallback_provider == "local" and s.llm_provider != "local") else None
    return _wrap(primary, fb)


def get_tool_model(tools: list[Any]) -> Runnable:
    s = get_settings()
    primary = _primary(json_mode=False).bind_tools(tools)
    fb = LocalAnalystModel().bind_tools(tools) if (s.llm_fallback_provider == "local" and s.llm_provider != "local") else None
    return _wrap(primary, fb)


def with_timeout(runnable: Runnable, seconds: float | None = None) -> Runnable:
    """İstənilən Runnable-a sərt timeout əlavə edir (provayderin öz timeout-undan əlavə)."""
    s = get_settings()
    secs = seconds or (s.ollama_timeout_s if s.llm_provider == "ollama" else s.llm_timeout_s)

    def _run(x: Any, config: RunnableConfig) -> Any:
        fut = _pool.submit(runnable.invoke, x, config)
        try:
            return fut.result(timeout=secs)
        except FutTimeout as exc:
            raise TimeoutError(f"LLM çağırışı {secs}s ərzində tamamlanmadı") from exc

    return RunnableLambda(_run, name=f"timeout[{getattr(runnable, 'name', None) or type(runnable).__name__}]")


def provider_info() -> dict[str, Any]:
    s = get_settings()
    model = {"local": "local-heuristic-v1", "ollama": s.ollama_model}.get(s.llm_provider, s.llm_model)
    return {"provider": s.llm_provider, "model": model,
            "fallback": s.llm_fallback_provider, "timeout_s": s.llm_timeout_s, "max_retries": s.llm_max_retries,
            "embeddings": s.embedding_provider}


def ollama_status() -> dict[str, Any]:
    """Ollama serveri işləyirmi və konfiqurasiya edilmiş model yüklənibmi (dashboard üçün)."""
    import httpx
    s = get_settings()
    try:
        r = httpx.get(f"{s.ollama_base_url}/api/tags", timeout=3)
        names = [m.get("name", "") for m in r.json().get("models", [])]
        want = s.ollama_model if ":" in s.ollama_model else s.ollama_model + ":latest"
        return {"reachable": True, "model": s.ollama_model, "model_pulled": want in names, "available": names}
    except Exception as exc:
        return {"reachable": False, "model": s.ollama_model, "error": type(exc).__name__}
