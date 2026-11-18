"""Ollama HTTP API-ni təqlid edən test serveri (/api/tags, /api/chat, NDJSON stream, tool_calls).

Cavabları oflayn LocalAnalystModel hesablayır — məqsəd modelin keyfiyyətini deyil, MediaOS ↔ Ollama
inteqrasiyasını (sorğu formatı, JSON rejimi, tool-calling, token sayları, keep_alive) real HTTP üzərində yoxlamaqdır.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.llm.local_model import LocalAnalystModel


class FakeOllama:
    def __init__(self, models=("qwen2.5:7b-instruct",)):
        self.models = list(models)
        self.requests: list[dict] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json"):
                data = body.encode() if isinstance(body, str) else body
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/api/tags":
                    self._send(200, json.dumps({"models": [{"name": m} for m in outer.models]}))
                else:
                    self._send(404, "{}")

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                outer.requests.append(body)
                if self.path != "/api/chat":
                    return self._send(404, "{}")
                if body.get("model") not in outer.models:
                    return self._send(404, json.dumps({"error": f"model '{body.get('model')}' not found"}))
                msgs = []
                for m in body.get("messages", []):
                    r, c = m.get("role"), m.get("content", "")
                    if r == "system":
                        msgs.append(SystemMessage(c))
                    elif r == "user":
                        msgs.append(HumanMessage(c))
                    elif r == "assistant":
                        tcs = [{"name": t["function"]["name"], "args": t["function"].get("arguments", {}),
                                "id": f"c{i}", "type": "tool_call"} for i, t in enumerate(m.get("tool_calls") or [])]
                        msgs.append(AIMessage(c, tool_calls=tcs))
                    elif r == "tool":
                        msgs.append(ToolMessage(c, tool_call_id="x"))
                model = LocalAnalystModel(bound_tools=body.get("tools") or [])
                ai = model._generate(msgs).generations[0].message
                out = {"model": body["model"], "created_at": "2026-11-18T00:00:00Z",
                       "message": {"role": "assistant", "content": ai.content,
                                   **({"tool_calls": [{"function": {"name": t["name"], "arguments": t["args"]}}
                                                      for t in ai.tool_calls]} if ai.tool_calls else {})},
                       "done": True, "done_reason": "stop",
                       "prompt_eval_count": ai.usage_metadata["input_tokens"], "eval_count": ai.usage_metadata["output_tokens"]}
                self._send(200, json.dumps(out) + "\n", "application/x-ndjson")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
