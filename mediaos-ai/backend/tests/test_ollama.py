"""Lokal LLM (Ollama) inteqrasiyası — real HTTP üzərində, Ollama API formatında test serveri ilə."""
import pytest

from app.config import get_settings
from tests.conftest import auth
from tests.fake_ollama import FakeOllama


@pytest.fixture
def ollama(monkeypatch):
    fake = FakeOllama()
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "ollama")
    monkeypatch.setattr(s, "ollama_base_url", fake.url)
    yield fake
    fake.close()


def test_structured_chain_uses_json_mode_and_keep_alive(ollama):
    from app.chains.news import relevance_chain
    d = relevance_chain().invoke({"title": "Astara gömrük postunda növbə", "body": "Astara gömrük postunda 5 saat növbə var.",
                                  "source_name": "x", "source_kind": "social"})
    assert d.decision in ("accept", "review") and d.result.is_relevant
    chat = [r for r in ollama.requests if "messages" in r]
    assert chat and chat[0]["model"] == "qwen2.5:7b-instruct"
    assert chat[0]["format"] == "json" and chat[0]["keep_alive"] == "10m"
    assert chat[0]["options"]["num_ctx"] == 8192 and chat[0]["options"]["temperature"] == 0


def test_agent_tool_calling_over_ollama(ollama, client):
    r = client.post("/api/chat", headers=auth("analyst"), json={"question": "Son 7 gündə mənfi rəylər hansı mövzularla bağlıdır?"})
    b = r.json()
    assert r.status_code == 200 and {"get_trends", "search_news"} <= {t["tool"] for t in b["tools"]}
    tool_reqs = [x for x in ollama.requests if x.get("tools")]
    assert tool_reqs and "format" not in {k for k, v in tool_reqs[0].items() if v}  # tool rejimində JSON rejimi yoxdur
    assert b["citations"]


def test_fallback_to_offline_model_when_ollama_down(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "ollama")
    monkeypatch.setattr(s, "ollama_base_url", "http://127.0.0.1:9")  # heç kim dinləmir
    monkeypatch.setattr(s, "llm_max_retries", 0)
    from app.chains.news import relevance_chain
    d = relevance_chain().invoke({"title": "Dövlət Gömrük Komitəsi", "body": "Dövlət Gömrük Komitəsi yeni xidmət təqdim edib",
                                  "source_name": "x", "source_kind": "official"})
    assert d.decision == "accept"  # Ollama əlçatmazdır → oflayn modelə keçid, sistem dayanmır


def test_health_reports_ollama_status(ollama, client):
    h = client.get("/health").json()["llm"]
    assert h["provider"] == "ollama" and h["model"] == "qwen2.5:7b-instruct"
    assert h["ollama"]["reachable"] and h["ollama"]["model_pulled"]
    ollama.models = ["llama3.1:8b"]
    assert client.get("/health").json()["llm"]["ollama"]["model_pulled"] is False
