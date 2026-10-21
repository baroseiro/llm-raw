"""Offline tests for the llm-raw harness.

The suite uses fake HTTP servers and fake subprocesses only. It never calls a
real model endpoint and never writes outside pytest's temporary directories.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

import llm_raw

ROOT = Path(__file__).resolve().parents[1]
SHIPPED_CONFIG = ROOT / "llm-raw.yaml"


# ---------------------------------------------------------------------------
# Helpers and fakes
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(
        self,
        body: bytes | str = b"",
        *,
        content_type: str = "application/json",
        status: int = 200,
        lines: list[bytes] | None = None,
    ):
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self._lines = lines or []
        self.headers = {"Content-Type": content_type}
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def read(self) -> bytes:
        return self._body

    def __iter__(self):
        return iter(self._lines)


def sse_lines(*objects: dict[str, Any]) -> list[bytes]:
    lines = [b": keep-alive\n"]
    for obj in objects:
        lines.append(b"data: " + json.dumps(obj).encode("utf-8") + b"\n\n")
    lines.append(b"data: [DONE]\n\n")
    return lines


def make_http_error(code: int, body: str = "error") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "http://127.0.0.1/v1/chat/completions",
        code,
        "error",
        {},
        io.BytesIO(body.encode("utf-8")),
    )


def stream_chunk(**delta: Any) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "model": "fake-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
    }


class SummaryClient:
    model = "summary-model"

    def __init__(self, summary: str = "A concise summary", error: Exception | None = None):
        self.summary = summary
        self.error = error
        self.calls: list[list[dict[str, Any]]] = []

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return {"content": self.summary}


class ScriptedClient:
    model = "scripted-model"

    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = responses
        self.calls: list[list[dict[str, Any]]] = []

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        self.calls.append(messages)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


def text_response(content: str = "ok", tool_calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "model": "fake-model",
        "content": content,
        "reasoning": "",
        "tool_calls": tool_calls or [],
        "finish_reason": "stop" if not tool_calls else "tool_calls",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "timings": {},
        "metrics": {"prompt_tokens": 10, "completion_tokens": 5, "streamed": False},
        "truncated": False,
        "streamed": False,
        "chunk_count": 0,
    }


@pytest.fixture()
def openai_server():
    """A tiny OpenAI-compatible HTTP server."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        state: dict[str, Any] = {"chat_calls": 0}

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, value: Any, status: int = 200) -> None:
            body = json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/props":
                self._json(
                    {
                        "model_path": "/models/fake.gguf",
                        "default_generation_settings": {"n_ctx": 8192},
                        "total_slots": 1,
                        "chat_template_caps": {"supports_tools": True},
                        "build_info": "fake",
                    }
                )
            elif self.path == "/v1/models":
                self._json({"data": [{"id": "fake-model"}]})
            elif self.path == "/health":
                self._json({"status": "ok", "service": "fake"})
            elif self.path == "/slots":
                self._json([{"id": 0}])
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path != "/v1/chat/completions":
                self._json({"error": "not found"}, 404)
                return
            Handler.state["chat_calls"] += 1
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                chunks = [
                    stream_chunk(reasoning_content="thinking"),
                    stream_chunk(content="hello "),
                    stream_chunk(content="world"),
                    {
                        "id": "chatcmpl-1",
                        "model": "fake-model",
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 11, "completion_tokens": 3},
                        "timings": {"prompt_ms": 10, "predicted_ms": 20},
                    },
                ]
                for chunk in chunks:
                    self.wfile.write(b"data: " + json.dumps(chunk).encode("utf-8") + b"\n\n")
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return
            self._json(
                {
                    "id": "chatcmpl-1",
                    "model": "fake-model",
                    "choices": [
                        {"index": 0, "message": {"content": "hello world"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 3},
                }
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield {"base_url": f"http://{host}:{port}/v1", "state": Handler.state}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# YAML and configuration
# ---------------------------------------------------------------------------


def test_yaml_subset_parses_mappings_lists_and_scalars() -> None:
    parsed = llm_raw.parse_yaml_subset(
        """
        # comment
        title: "hello # not a comment"
        enabled: true
        count: 3
        ratio: 0.5
        nothing: null
        empty_list: []
        inline: [a, "b", 2]
        nested:
          key: value
        servers:
          - name: one
            url: http://127.0.0.1
          - name: two
        """
    )
    assert parsed["title"] == "hello # not a comment"
    assert parsed["enabled"] is True
    assert parsed["count"] == 3
    assert parsed["ratio"] == 0.5
    assert parsed["nothing"] is None
    assert parsed["empty_list"] == []
    assert parsed["inline"] == ["a", "b", 2]
    assert parsed["nested"]["key"] == "value"
    assert parsed["servers"][0]["name"] == "one"
    assert parsed["servers"][1]["name"] == "two"


def test_shipped_config_parses_and_has_no_legacy_values() -> None:
    config = llm_raw.load_yaml(SHIPPED_CONFIG)
    assert config["endpoint"]["base_url"] == "http://127.0.0.1:8080/v1"
    assert config["logging"]["directory"] == "./llm-raw-logs"
    assert config["security"]["denied_tools"] == ["shell*", "exec*", "system*"]
    assert len(config["security"]["redact_patterns"]) == 3
    assert "\\s" in config["security"]["redact_patterns"][0]


def test_load_config_rejects_missing_explicit_file(tmp_path: Path) -> None:
    with pytest.raises(llm_raw.ConfigError, match="not found"):
        llm_raw.load_config(tmp_path / "missing.yaml")


def test_config_discovery_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(llm_raw.CONFIG_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm_raw, "MODULE_DIR", tmp_path / "module")
    assert llm_raw.default_config_path() == tmp_path / "module" / llm_raw.CONFIG_NAME

    local = tmp_path / llm_raw.CONFIG_NAME
    local.write_text("endpoint:\n  model: local\n", encoding="utf-8")
    assert llm_raw.default_config_path() == local

    explicit_env = tmp_path / "env.yaml"
    explicit_env.write_text("endpoint:\n  model: env\n", encoding="utf-8")
    monkeypatch.setenv(llm_raw.CONFIG_ENV, str(explicit_env))
    assert llm_raw.default_config_path() == explicit_env


def test_builtin_defaults_work_without_a_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(llm_raw.CONFIG_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm_raw, "MODULE_DIR", tmp_path / "module")
    config = llm_raw.load_config()
    assert config["endpoint"]["base_url"] == "http://127.0.0.1:8080/v1"
    assert config["hil"]["mode"] == "ask"


def test_expand_env_recurses() -> None:
    os.environ["LLM_RAW_TEST_VALUE"] = "expanded"
    try:
        value = llm_raw.expand_env(
            {"a": "${LLM_RAW_TEST_VALUE}", "b": ["{env:LLM_RAW_TEST_VALUE}"], "c": 1}
        )
    finally:
        os.environ.pop("LLM_RAW_TEST_VALUE", None)
    assert value == {"a": "expanded", "b": ["expanded"], "c": 1}


def test_build_config_cli_overrides() -> None:
    args = llm_raw.parse_args(
        [
            "--base-url",
            "http://example.test/v1",
            "--model",
            "m",
            "--temperature",
            "0.7",
            "--max-steps",
            "3",
            "--no-compact",
            "--no-log",
            "--yes",
        ]
    )
    config = llm_raw.build_config(args)
    assert config["endpoint"]["base_url"] == "http://example.test/v1"
    assert config["endpoint"]["model"] == "m"
    assert config["generation"]["temperature"] == 0.7
    assert config["max_steps"] == 3
    assert config["compaction"]["enabled"] is False
    assert config["logging"]["enabled"] is False
    assert config["hil"]["mode"] == "auto"


# ---------------------------------------------------------------------------
# URL, transport, SSE, retries, metrics
# ---------------------------------------------------------------------------


def test_url_normalization() -> None:
    assert llm_raw.normalize_urls("http://localhost:8080") == (
        "http://localhost:8080/v1",
        "http://localhost:8080",
    )
    assert llm_raw.normalize_urls("localhost:8080/v1/") == (
        "http://localhost:8080/v1",
        "http://localhost:8080",
    )
    assert llm_raw.normalize_urls("https://host/v1/chat/completions") == (
        "https://host/v1",
        "https://host",
    )


def test_headers_include_agent_and_bearer_token() -> None:
    headers = llm_raw.request_headers("secret", stream=True)
    assert headers["Authorization"] == "Bearer secret"
    assert headers["Accept"] == "text/event-stream"
    assert headers["User-Agent"].startswith("llm-raw/")


def test_stream_parses_content_reasoning_tools_usage_and_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    objects = [
        stream_chunk(reasoning_content="think"),
        stream_chunk(content="Hello"),
        stream_chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "call_1",
                    "function": {"name": "echo", "arguments": '{"x":'},
                }
            ]
        ),
        stream_chunk(
            tool_calls=[
                {"index": 0, "function": {"arguments": "1}"}},
            ]
        ),
        {
            "id": "chatcmpl-1",
            "model": "fake-model",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            "timings": {"prompt_ms": 100, "predicted_ms": 200},
        },
    ]
    monkeypatch.setattr(
        llm_raw.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(content_type="text/event-stream", lines=sse_lines(*objects)),
    )
    result = llm_raw.complete_payload(
        "http://fake/v1",
        None,
        {"model": "m", "messages": [], "stream": True},
        retries=0,
    )
    assert result["content"] == "Hello"
    assert result["reasoning"] == "think"
    assert result["tool_calls"][0]["id"] == "call_1"
    assert result["tool_calls"][0]["function"]["name"] == "echo"
    assert result["tool_calls"][0]["function"]["arguments"] == '{"x":1}'
    assert result["finish_reason"] == "tool_calls"
    assert result["usage"] == {"prompt_tokens": 12, "completion_tokens": 4}
    assert result["chunk_count"] == 5
    assert result["streamed"] is True
    assert result["metrics"]["prompt_tokens"] == 12
    assert result["metrics"]["completion_tokens"] == 4
    assert result["metrics"]["ttft_ms"] is not None


def test_stream_capture_raw_events(monkeypatch: pytest.MonkeyPatch) -> None:
    objects = [stream_chunk(content="x")]
    monkeypatch.setattr(
        llm_raw.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(content_type="text/event-stream", lines=sse_lines(*objects)),
    )
    result = llm_raw._stream_chat(
        "http://fake/v1",
        None,
        {"model": "m", "messages": [], "stream": True},
        timeout=1,
        capture_raw=True,
    )
    assert result["raw_events"] == objects


def test_stream_can_fall_back_to_plain_json(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(
        {
            "id": "chatcmpl-json",
            "model": "m",
            "choices": [{"message": {"content": "not streamed"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }
    )
    monkeypatch.setattr(
        llm_raw.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(body, content_type="application/json"),
    )
    result = llm_raw._stream_chat(
        "http://fake/v1",
        None,
        {"model": "m", "messages": [], "stream": True},
        timeout=1,
    )
    assert result["content"] == "not streamed"
    assert result["streamed"] is False
    assert result["metrics"]["prompt_tokens"] == 1


def test_stream_error_object_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    objects = [{"error": {"message": "bad request"}}]
    monkeypatch.setattr(
        llm_raw.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(content_type="text/event-stream", lines=sse_lines(*objects)),
    )
    with pytest.raises(llm_raw.LLMError, match="bad request"):
        llm_raw.complete_payload("http://fake/v1", None, {"model": "m", "messages": [], "stream": True}, retries=0)


def test_retry_policy_retries_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        calls["count"] += 1
        if calls["count"] == 1:
            raise make_http_error(500)
        return FakeResponse(
            json.dumps(
                {
                    "id": "id",
                    "model": "m",
                    "choices": [{"message": {"content": "recovered"}, "finish_reason": "stop"}],
                }
            )
        )

    monkeypatch.setattr(llm_raw.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_raw.time, "sleep", lambda seconds: None)
    result = llm_raw.complete_payload(
        "http://fake/v1",
        None,
        {"model": "m", "messages": [], "stream": False},
        retries=2,
    )
    assert result["content"] == "recovered"
    assert calls["count"] == 2


def test_retry_policy_does_not_retry_400(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        calls["count"] += 1
        raise make_http_error(400, "bad input")

    monkeypatch.setattr(llm_raw.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(llm_raw.LLMError, match="HTTP 400"):
        llm_raw.complete_payload(
            "http://fake/v1",
            None,
            {"model": "m", "messages": [], "stream": False},
            retries=3,
        )
    assert calls["count"] == 1


def test_retry_policy_retries_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.URLError("refused")
        return FakeResponse(json.dumps({"id": "id", "model": "m", "choices": []}))

    monkeypatch.setattr(llm_raw.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_raw.time, "sleep", lambda seconds: None)
    result = llm_raw.complete_payload(
        "http://fake/v1",
        None,
        {"model": "m", "messages": [], "stream": False},
        retries=1,
    )
    assert result["content"] == ""
    assert calls["count"] == 2


def test_metrics_estimate_tokens_and_draft_acceptance() -> None:
    metrics = llm_raw.build_metrics(
        10.0,
        11.0,
        None,
        None,
        {},
        {
            "prompt_n": 100,
            "predicted_n": 20,
            "prompt_ms": 1000,
            "predicted_ms": 2000,
            "draft_n": 10,
            "draft_n_accepted": 7,
        },
        "abcdefgh",
        "",
        [],
        False,
    )
    assert metrics["prompt_tokens"] == 100
    assert metrics["completion_tokens"] == 20
    assert metrics["server_prefill_tps"] == 100
    assert metrics["server_decode_tps"] == 10
    assert metrics["draft_acceptance"] == 0.7
    assert metrics["estimated_completion_tokens"] is False


def test_metrics_without_server_usage_are_estimated() -> None:
    metrics = llm_raw.build_metrics(0.0, 1.0, None, None, {}, {}, "12345678", "", [], True)
    assert metrics["completion_tokens"] == 2
    assert metrics["estimated_completion_tokens"] is True
    assert metrics["ttft_ms"] is None
    assert metrics["server_prefill_tps"] is None


def test_non_stream_parsing_keeps_raw_object() -> None:
    obj = {
        "id": "id",
        "model": "m",
        "choices": [{"message": {"content": "hello"}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }
    result = llm_raw._parse_completion_object(obj, 0.0, 1.0, False)
    assert result["content"] == "hello"
    assert result["truncated"] is True
    assert result["raw"] is obj


# ---------------------------------------------------------------------------
# Redaction and logging
# ---------------------------------------------------------------------------


def test_redact_text_removes_bearer_keys_and_patterns() -> None:
    text = "Authorization: Bearer abc123 key=sk-123456789012 and api_key: topsecret"
    redacted = llm_raw.redact_text(
        text,
        [r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*", r"(?i)sk-[A-Za-z0-9_-]{12,}", r"(?i)api[_-]?key\s*[:=]\s*[^\s,}]+"],
        ["topsecret"],
    )
    assert "abc123" not in redacted
    assert "sk-123456789012" not in redacted
    assert "topsecret" not in redacted
    assert "[REDACTED]" in redacted


def test_redactor_hides_sensitive_keys_recursively() -> None:
    redactor = llm_raw.Redactor([], ["secret"])
    result = redactor.value(
        {
            "authorization": "Bearer abc",
            "nested": {"api_key": "value", "list": ["secret", "safe"]},
            "token": "x",
        }
    )
    assert result["authorization"] == "[REDACTED]"
    assert result["nested"]["api_key"] == "[REDACTED]"
    assert result["nested"]["list"] == ["[REDACTED]", "safe"]
    assert result["token"] == "[REDACTED]"


def test_event_logger_writes_valid_jsonl_and_redacts(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    redactor = llm_raw.Redactor([r"(?i)bearer\s+\S+"], ["secret-token"])
    logger = llm_raw.EventLogger(log_dir, True, False, redactor, "test")
    logger.log("request", payload={"authorization": "Bearer abc", "text": "secret-token"})
    logger.close()
    assert logger.path is not None
    lines = logger.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert events[0]["event"] == "session_start"
    assert events[1]["event"] == "request"
    assert "secret-token" not in json.dumps(events)
    assert "Bearer abc" not in json.dumps(events)


# ---------------------------------------------------------------------------
# Security and HIL
# ---------------------------------------------------------------------------


def test_security_policy_denies_and_allows() -> None:
    policy = llm_raw.SecurityPolicy(
        {
            "denied_tools": ["shell*", "exec*"],
            "allowed_tools": [],
            "max_tool_result_chars": 5,
        }
    )
    assert policy.tool_allowed("echo") is True
    assert policy.tool_allowed("shell_exec") is False
    assert policy.tool_allowed("execute") is False

    restricted = llm_raw.SecurityPolicy({"allowed_tools": ["safe_*"]})
    assert restricted.tool_allowed("safe_read") is True
    assert restricted.tool_allowed("other") is False


def test_policy_wraps_and_truncates_results() -> None:
    policy = llm_raw.SecurityPolicy({"max_tool_result_chars": 5})
    wrapped = policy.wrap_result("echo", "abcdefghij", False, False)
    assert '<tool_result name="echo"' in wrapped
    assert 'trust="untrusted"' in wrapped
    assert "abcde" in wrapped
    assert "truncated 5 chars" in wrapped


def test_approval_modes_and_auto_approve() -> None:
    security = llm_raw.SecurityPolicy({})
    callback_calls: list[str] = []

    def callback(name: str, args: dict[str, Any], source: str, trusted: bool) -> llm_raw.ApprovalDecision:
        callback_calls.append(name)
        return llm_raw.ApprovalDecision(True, "user approved", always=name == "always_tool")

    ask = llm_raw.ApprovalManager({"mode": "ask", "auto_approve": ["auto_*"]}, security, callback)
    assert ask.decide("ask_tool", {}, "test", True).allowed is True
    assert ask.decide("auto_tool", {}, "test", True).reason == "auto-approved by policy"
    assert ask.decide("always_tool", {}, "test", True).always is True
    ask.always.add("always_tool")
    assert ask.decide("always_tool", {}, "test", True).reason == "approved for this session"
    assert callback_calls == ["ask_tool", "always_tool"]

    auto = llm_raw.ApprovalManager({"mode": "auto"}, security, callback)
    assert auto.decide("anything", {}, "test", False).allowed is True

    deny = llm_raw.ApprovalManager({"mode": "deny"}, security, callback)
    assert deny.decide("anything", {}, "test", True).allowed is False

    no_callback = llm_raw.ApprovalManager({"mode": "ask"}, security, None)
    decision = no_callback.decide("needs_approval", {}, "test", True)
    assert decision.allowed is False
    assert "no interactive approver" in decision.reason

    blocked = llm_raw.ApprovalManager({"mode": "auto"}, llm_raw.SecurityPolicy({"denied_tools": ["bad"]}), None)
    assert blocked.decide("bad", {}, "test", True).allowed is False


def test_tool_registry_executes_and_handles_errors() -> None:
    security = llm_raw.SecurityPolicy({})
    registry = llm_raw.ToolRegistry(security)
    registry.register(
        llm_raw.ToolSpec(
            name="echo",
            description="Echo text",
            parameters={"type": "object"},
            source="test",
            trust=True,
            handler=lambda args: llm_raw.ToolResult(str(args.get("text", "")), args, False),
        )
    )
    registry.register(
        llm_raw.ToolSpec(
            name="broken",
            description="Raise",
            parameters={"type": "object"},
            source="test",
            trust=True,
            handler=lambda args: (_ for _ in ()).throw(RuntimeError("boom")),
        )
    )
    approver = llm_raw.ApprovalManager({"mode": "auto"}, security, None)
    result = registry.execute("echo", {"text": "hi"}, approver)
    assert "hi" in result.text
    assert result.is_error is False
    unknown = registry.execute("missing", {}, approver)
    assert "unknown tool" in unknown.text
    assert unknown.is_error is True
    broken = registry.execute("broken", {}, approver)
    assert "boom" in broken.text
    assert broken.is_error is True


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


def test_skill_registry_scans_frontmatter_and_loads(tmp_path: Path) -> None:
    base = tmp_path / "skills"
    base.mkdir()
    (base / "root.md").write_text(
        "---\nname: root-skill\ndescription: \"Root description\"\n---\nRoot body",
        encoding="utf-8",
    )
    nested = base / "nested"
    nested.mkdir()
    (nested / "SKILL.md").write_text(
        "---\nname: nested-skill\ndescription: Nested\n---\nNested body",
        encoding="utf-8",
    )
    registry = llm_raw.SkillRegistry([str(base)], max_chars=1000)
    listed = registry.list()
    assert [item["id"] for item in listed] == ["nested-skill", "root-skill"]
    assert registry.load("root-skill") == "Root body"
    assert registry.load("nested-skill") == "Nested body"
    assert "Root description" in listed[1]["description"]
    with pytest.raises(llm_raw.LLMError, match="Unknown skill"):
        registry.load("missing")


def test_skill_tools_are_auto_approved_and_wrapped(tmp_path: Path) -> None:
    base = tmp_path / "skills"
    base.mkdir()
    (base / "one.md").write_text("---\nname: one\ndescription: One\n---\nBody", encoding="utf-8")
    skills = llm_raw.SkillRegistry([str(base)])
    registry = llm_raw.ToolRegistry(llm_raw.SecurityPolicy({}))
    registry.register_skills(skills)
    approver = llm_raw.ApprovalManager({"mode": "ask", "auto_approve": ["list_skills", "load_skill"]}, registry.security, None)
    listed = registry.execute("list_skills", {}, approver)
    assert "one" in listed.text
    loaded = registry.execute("load_skill", {"id": "one"}, approver)
    assert "Body" in loaded.text
    assert "<tool_result" in loaded.text


def test_max_chars_truncates_skill_body(tmp_path: Path) -> None:
    path = tmp_path / "long.md"
    path.write_text("---\nname: long\ndescription: Long\n---\n" + "x" * 100, encoding="utf-8")
    registry = llm_raw.SkillRegistry([str(path)], max_chars=10)
    assert registry.load("long") == "x" * 10


# ---------------------------------------------------------------------------
# Compaction and sessions
# ---------------------------------------------------------------------------


def test_estimate_tokens() -> None:
    assert llm_raw.estimate_tokens("") == 1
    assert llm_raw.estimate_tokens("abcd") == 1
    assert llm_raw.estimate_tokens("a" * 40) == 10


def test_compaction_preserves_system_and_tool_pairs() -> None:
    client = SummaryClient("summary text")
    compactor = llm_raw.Compactor(
        client,
        {"enabled": True, "threshold_ratio": 0.1, "keep_recent": 2, "strategy": "summarize"},
    )
    messages = [
        {"role": "system", "content": "base system"},
        {"role": "user", "content": "old question"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "middle question"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "content": "tool result"},
        {"role": "user", "content": "recent question"},
    ]
    compacted, changed = compactor.maybe_compact(messages, context_window=100)
    assert changed is True
    assert compacted[0] == {"role": "system", "content": "base system"}
    assert compacted[1]["role"] == "system"
    assert "summary text" in compacted[1]["content"]
    assert compacted[2]["role"] == "assistant"
    assert compacted[3]["role"] == "tool"
    assert compacted[-1]["content"] == "recent question"


def test_compaction_does_not_run_below_threshold() -> None:
    client = SummaryClient()
    compactor = llm_raw.Compactor(client, {"enabled": True, "threshold_ratio": 0.9, "keep_recent": 2})
    messages = [{"role": "user", "content": "short"}]
    compacted, changed = compactor.maybe_compact(messages, context_window=1000)
    assert changed is False
    assert compacted == messages
    assert client.calls == []


def test_compaction_falls_back_when_summary_fails() -> None:
    client = SummaryClient(error=RuntimeError("no model"))
    compactor = llm_raw.Compactor(
        client,
        {"enabled": True, "threshold_ratio": 0.01, "keep_recent": 2, "strategy": "summarize"},
    )
    messages = [
        {"role": "user", "content": "older question"},
        {"role": "assistant", "content": "older answer"},
        {"role": "user", "content": "middle"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "newest"},
    ]
    compacted, changed = compactor.maybe_compact(messages, context_window=10)
    assert changed is True
    summary = compacted[0]["content"]
    assert "older question" in summary
    assert "no summary available" not in summary


def test_session_runs_tool_loop_and_returns_final_answer() -> None:
    client = ScriptedClient(
        [
            text_response(
                "",
                [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "echo", "arguments": '{"text":"hello"}'},
                    }
                ],
            ),
            text_response("final answer"),
        ]
    )
    security = llm_raw.SecurityPolicy({})
    registry = llm_raw.ToolRegistry(security)
    registry.register(
        llm_raw.ToolSpec(
            name="echo",
            description="Echo",
            parameters={"type": "object"},
            source="test",
            trust=True,
            handler=lambda args: llm_raw.ToolResult("echo:" + str(args["text"]), None, False),
        )
    )
    approver = llm_raw.ApprovalManager({"mode": "auto"}, security, None)
    session = llm_raw.Session(
        client,
        {"system_prompt": "sys", "max_steps": 3, "stream": False, "generation": {}},
        registry,
        None,
        None,
        approver,
    )
    result = session.send("do it")
    assert result["content"] == "final answer"
    assert len(client.calls) == 2
    tool_messages = [m for m in session.messages if m["role"] == "tool"]
    assert len(tool_messages) == 1
    assert "echo:hello" in tool_messages[0]["content"]
    assert "<tool_result" in tool_messages[0]["content"]


def test_session_denied_tool_returns_denial_to_model() -> None:
    client = ScriptedClient(
        [
            text_response(
                "",
                [{"id": "c1", "type": "function", "function": {"name": "echo", "arguments": "{}"}}],
            ),
            text_response("done"),
        ]
    )
    security = llm_raw.SecurityPolicy({})
    registry = llm_raw.ToolRegistry(security)
    registry.register(
        llm_raw.ToolSpec(
            name="echo",
            description="Echo",
            parameters={"type": "object"},
            source="test",
            trust=True,
            handler=lambda args: llm_raw.ToolResult("should not run", None, False),
        )
    )
    approver = llm_raw.ApprovalManager({"mode": "deny"}, security, None)
    session = llm_raw.Session(client, {"max_steps": 2, "stream": False}, registry, None, None, approver)
    result = session.send("go")
    assert result["content"] == "done"
    tool_messages = [m for m in session.messages if m["role"] == "tool"]
    assert "DENIED" in tool_messages[0]["content"]


def test_session_tool_call_limit() -> None:
    client = ScriptedClient(
        [
            text_response(
                "",
                [{"id": "c1", "type": "function", "function": {"name": "echo", "arguments": "{}"}}],
            ),
            text_response("done"),
        ]
    )
    security = llm_raw.SecurityPolicy({"max_tool_calls": 0})
    registry = llm_raw.ToolRegistry(security)
    registry.register(
        llm_raw.ToolSpec(
            name="echo",
            description="Echo",
            parameters={"type": "object"},
            source="test",
            trust=True,
            handler=lambda args: llm_raw.ToolResult("ran", None, False),
        )
    )
    approver = llm_raw.ApprovalManager({"mode": "auto"}, security, None)
    session = llm_raw.Session(client, {"max_steps": 2, "stream": False}, registry, None, None, approver)
    session.send("go")
    tool_messages = [m for m in session.messages if m["role"] == "tool"]
    assert "maximum tool calls" in tool_messages[0]["content"]


def test_session_save_and_load(tmp_path: Path) -> None:
    client = ScriptedClient([text_response("hello")])
    session = llm_raw.Session(client, {"system_prompt": "sys", "stream": False, "max_steps": 1})
    session.send("hi")
    path = tmp_path / "session.json"
    session.save(path)
    loaded = llm_raw.Session(ScriptedClient([text_response("ignored")]), {"system_prompt": "other"})
    loaded.load(path)
    assert loaded.base_system == "sys"
    assert loaded.messages == session.messages
    assert path.read_text(encoding="utf-8").startswith("{")


# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------


def test_mcp_tool_names_are_namespaced_and_length_safe() -> None:
    assert llm_raw._mcp_tool_name("server", "echo") == "mcp__server__echo"
    long_name = llm_raw._mcp_tool_name("s" * 80, "t" * 80)
    assert len(long_name) <= 64
    assert long_name.startswith("mcp__")
    assert long_name == llm_raw._mcp_tool_name("s" * 80, "t" * 80)


def test_mcp_result_to_text() -> None:
    result = {
        "content": [
            {"type": "text", "text": "hello"},
            {"type": "image", "mimeType": "image/png"},
            {"type": "resource", "resource": {"uri": "file:///x"}},
        ],
        "structuredContent": {"ok": True},
    }
    text = llm_raw.mcp_result_to_text(result)
    assert "hello" in text
    assert "[image image/png]" in text
    assert "file:///x" in text
    assert '"ok": true' in text


def test_http_mcp_client_handles_notifications_empty_responses() -> None:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, value: Any) -> None:
            body = json.dumps(value).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if "id" not in payload:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            method = payload.get("method")
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {}}
            elif method == "tools/list":
                result = {"tools": [{"name": "echo", "description": "Echo", "inputSchema": {"type": "object"}}]}
            elif method == "tools/call":
                result = {"content": [{"type": "text", "text": "echoed"}]}
            else:
                result = {}
            self._send({"jsonrpc": "2.0", "id": payload["id"], "result": result})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    client = llm_raw.HttpMCPClient("remote", f"http://{host}:{port}/mcp", timeout=3)
    try:
        initialized = client.initialize()
        assert initialized["protocolVersion"] == "2024-11-05"
        tools = client.list_tools()
        assert tools[0]["name"] == "echo"
        result = client.call_tool("echo", {"text": "hi"})
        assert result["content"][0]["text"] == "echoed"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_stdio_mcp_client_round_trip(tmp_path: Path) -> None:
    script = tmp_path / "fake_mcp.py"
    script.write_text(
        """
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    if "id" not in message:
        continue
    method = message.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {}}
    elif method == "tools/list":
        result = {"tools": [{"name": "echo", "description": "Echo", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        text = "echo:" + json.dumps(message["params"]["arguments"])
        result = {"content": [{"type": "text", "text": text}]}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
""",
        encoding="utf-8",
    )
    client = llm_raw.StdioMCPClient("local", [sys.executable, str(script)], timeout=10)
    try:
        client.initialize()
        tools = client.list_tools()
        assert tools[0]["name"] == "echo"
        result = client.call_tool("echo", {"text": "hi"})
        assert "echo:" in result["content"][0]["text"]
    finally:
        client.close()


def test_mcp_manager_starts_registers_and_calls(tmp_path: Path) -> None:
    script = tmp_path / "fake_mcp.py"
    script.write_text(
        """
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    if "id" not in message:
        continue
    method = message.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {}}
    elif method == "tools/list":
        result = {"tools": [{"name": "echo", "description": "Echo", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": "called"}]}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
""",
        encoding="utf-8",
    )
    manager = llm_raw.MCPManager(
        {"servers": {"local": {"transport": "stdio", "command": [sys.executable, str(script)], "trust": False}}}
    )
    try:
        manager.start()
        assert manager.errors == []
        assert "mcp__local__echo" in manager.tools
        registry = llm_raw.ToolRegistry(llm_raw.SecurityPolicy({}))
        registry.register_mcp(manager)
        approver = llm_raw.ApprovalManager({"mode": "auto"}, registry.security, None)
        result = registry.execute("mcp__local__echo", {}, approver)
        assert "called" in result.text
    finally:
        manager.close()


# ---------------------------------------------------------------------------
# Local endpoint and CLI integration
# ---------------------------------------------------------------------------


def test_http_endpoint_non_stream_and_discovery(openai_server: dict[str, Any]) -> None:
    client = llm_raw.RawClient(base_url=openai_server["base_url"], model="fake-model", retries=0)
    discovery = client.discover()
    assert discovery["model"] == "fake-model"
    assert discovery["model_props"]["n_ctx"] == 8192
    assert discovery["model_props"]["supports_tools"] is True
    assert discovery["model_props"]["discovery_errors"] == []

    result = client.chat(
        [{"role": "user", "content": "hi"}],
        params={"temperature": 0.0},
        stream=False,
    )
    assert result["content"] == "hello world"
    assert result["usage"]["prompt_tokens"] == 11
    assert result["streamed"] is False


def test_http_endpoint_streaming(openai_server: dict[str, Any]) -> None:
    client = llm_raw.RawClient(base_url=openai_server["base_url"], model="fake-model", retries=0)
    deltas: list[tuple[str, str]] = []
    result = client.chat(
        [{"role": "user", "content": "hi"}],
        stream=True,
        on_delta=lambda kind, text: deltas.append((kind, text)),
    )
    assert result["content"] == "hello world"
    assert result["reasoning"] == "thinking"
    assert result["streamed"] is True
    assert result["metrics"]["prompt_tokens"] == 11
    assert ("content", "hello ") in deltas
    assert ("reasoning", "thinking") in deltas


def test_cli_lists_skills_and_tools(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "one.md").write_text("---\nname: one\ndescription: One\n---\nBody", encoding="utf-8")

    assert llm_raw.main(["--list-skills", "--no-log", "--skills", str(skills)]) == 0
    output = capsys.readouterr().out
    assert '"id": "one"' in output

    assert llm_raw.main(["--list-tools", "--no-log", "--skills", str(skills)]) == 0
    output = capsys.readouterr().out
    assert "list_skills" in output
    assert "load_skill" in output


def test_cli_version_and_missing_config(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        llm_raw.main(["--version"])
    assert exc.value.code == 0
    assert "llm-raw 0.2.0" in capsys.readouterr().out

    code = llm_raw.main(["--config", str(tmp_path / "missing.yaml"), "--list-skills"])
    assert code == 2
    assert "Config file not found" in capsys.readouterr().err


def test_cli_one_shot_against_fake_endpoint(
    openai_server: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    code = llm_raw.main(
        [
            "--base-url",
            openai_server["base_url"],
            "--model",
            "fake-model",
            "--prompt",
            "hello",
            "--no-stream",
            "--no-log",
            "--json",
        ]
    )
    assert code == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["content"] == "hello world"
    assert result["metrics"]["prompt_tokens"] == 11


def test_cli_one_shot_stream_against_fake_endpoint(
    openai_server: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    code = llm_raw.main(
        [
            "--base-url",
            openai_server["base_url"],
            "--model",
            "fake-model",
            "--prompt",
            "hello",
            "--no-log",
        ]
    )
    assert code == 0
    assert "hello world" in capsys.readouterr().out


def test_cli_logging_writes_redacted_jsonl(
    openai_server: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_dir = tmp_path / "logs"
    code = llm_raw.main(
        [
            "--base-url",
            openai_server["base_url"],
            "--model",
            "fake-model",
            "--prompt",
            "hello",
            "--no-stream",
            "--log-dir",
            str(log_dir),
        ]
    )
    assert code == 0
    capsys.readouterr()
    files = list(log_dir.glob("*.jsonl"))
    assert len(files) == 1
    events = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    names = [event["event"] for event in events]
    assert "session_start" in names
    assert "request" in names
    assert "response" in names
    assert "fake-model" in files[0].read_text(encoding="utf-8")


def test_python_api_import_has_no_side_effects(tmp_path: Path) -> None:
    code = "import llm_raw; print(llm_raw.VERSION); print(llm_raw.main.__name__)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "0.2.0\nmain"
