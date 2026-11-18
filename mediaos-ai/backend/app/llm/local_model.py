"""LangChain Chat Model interfeysini tam reallaşdıran oflayn model.

`BaseChatModel`-dən törəyir, ona görə LCEL zəncirlərində, `bind_tools` ilə tool-calling-də,
callback-lərdə (token/latency ölçümü) real provayderlə eyni şəkildə işləyir.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.llm import heuristics as H


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _field(text: str, name: str) -> str:
    m = re.search(rf"^{name}:\s*(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


def _tag(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>\n?(.*?)\n?</{tag}>", text, re.S)
    return m.group(1) if m else ""


class LocalAnalystModel(BaseChatModel):
    model_name: str = "local-heuristic-v1"
    bound_tools: list[dict[str, Any]] = []
    fail_always: bool = False  # testlərdə fallback/retry yoxlamaq üçün

    @property
    def _llm_type(self) -> str:
        return "local-heuristic"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model_name": self.model_name}

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # type: ignore[override]
        return self.model_copy(update={"bound_tools": [convert_to_openai_tool(t) for t in tools]})

    # ------------------------------------------------------------------
    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        if self.fail_always:
            raise RuntimeError("local model: süni xəta (test)")
        system = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        task_m = re.search(r"\[task=(\w+)\]", str(system))
        task = task_m.group(1) if task_m else "chat"
        human = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        human = human if isinstance(human, str) else json.dumps(human, ensure_ascii=False)

        if task == "agent":
            msg = self._agent_step(messages, str(system))
        else:
            payload = self._structured(task, human)
            msg = AIMessage(content=json.dumps(payload, ensure_ascii=False))

        in_tok = sum(_approx_tokens(str(m.content)) for m in messages)
        out_tok = _approx_tokens(str(msg.content) + json.dumps(msg.tool_calls, ensure_ascii=False, default=str))
        msg.usage_metadata = {"input_tokens": in_tok, "output_tokens": out_tok, "total_tokens": in_tok + out_tok}
        msg.response_metadata = {"model_name": self.model_name}
        return ChatResult(generations=[ChatGeneration(message=msg)],
                          llm_output={"token_usage": msg.usage_metadata, "model_name": self.model_name})

    def _structured(self, task: str, human: str) -> dict[str, Any]:
        src = _tag(human, "source_text")
        title = _field(human, "Başlıq")
        if task == "relevance":
            kind = re.search(r"növ:\s*(\w+)", human)
            return H.relevance(title, src, kind.group(1) if kind else "media")
        if task == "category":
            return H.category(title, src)
        if task == "sentiment":
            return H.sentiment(title, src, _field(human, "Növ"))
        if task == "risk":
            head = _field(human, "Növ")
            ctype = head.split(";")[0].strip()
            sent = re.search(r"Sentiment:\s*(\w+)", human)
            mentions = re.search(r"Təkrar mənbə sayı:\s*(\d+)", human)
            return H.risk(title, src, ctype, sent.group(1) if sent else "neutral",
                          int(mentions.group(1)) if mentions else 1, _tag(human, "context"))
        if task == "factcheck":
            return H.fact_check(_field(human, "İddia"), _tag(human, "context"))
        if task == "rag":
            return H.rag_answer(_field(human, "Sual"), _tag(human, "context"))
        if task == "summary":
            return H.executive_summary(_field(human, "Dövr"), _field(human, "Statistika"), _tag(human, "context"))
        return {"answer": "Naməlum tapşırıq", "confidence": 0.0}

    def _agent_step(self, messages: list[BaseMessage], system: str) -> AIMessage:
        last_h = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        question = str(messages[last_h].content)
        after = messages[last_h + 1:]
        tool_msgs = [m for m in after if isinstance(m, ToolMessage)]
        if tool_msgs:
            results = []
            for tm in tool_msgs:
                try:
                    results.append(json.loads(tm.content) if isinstance(tm.content, str) else tm.content)
                except json.JSONDecodeError:
                    results.append({"tool": tm.name, "error": str(tm.content)[:200]})
            return AIMessage(content=H.compose_answer(question, results))

        history = []
        for m in messages[:last_h]:
            if isinstance(m, HumanMessage):
                history.append(("human", str(m.content)))
            elif isinstance(m, AIMessage) and m.content:
                history.append(("ai", str(m.content)))
        today_m = re.search(r"Bu günün tarixi:\s*(\d{4}-\d{2}-\d{2})", system)
        today = date.fromisoformat(today_m.group(1)) if today_m else date.today()
        names = {t["function"]["name"] for t in self.bound_tools}
        plan = H.plan_tools(question, history, names, today)
        if not plan:
            return AIMessage(content="Bu sualı mövcud alətlərlə cavablandıra bilmirəm. Sualı DGK media monitorinqi çərçivəsində dəqiqləşdirin.")
        return AIMessage(content="", tool_calls=[
            {"name": c["name"], "args": c["args"], "id": f"call_{uuid.uuid4().hex[:10]}", "type": "tool_call"} for c in plan
        ])
