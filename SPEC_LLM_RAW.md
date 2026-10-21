# SPEC_LLM_RAW.md

Status: **v0.1.0 implemented** (portable single-file harness)  
Owners: llm-eval project  
Scope: raw LLM transport, sessions, tools, skills, HIL, security, compaction, logging, TUI  
Related: `PLAN_LLM_RAW.md`, `.agents/skills/llm-eval/scripts/llm_raw.py`, `.agents/skills/llm-eval/scripts/llm_raw.yaml`

---

## 1. Purpose

`llm_raw.py` is a **general-purpose raw LLM harness** for any OpenAI-compatible `/v1/chat/completions` endpoint. It is deliberately independent of the evaluation suite.

The evaluation tool (`eval_llm.py`) owns:

- quality suites and rubrics
- deterministic performance prompts
- automatic checks
- run artifacts and reports
- blind-judge packet inputs

`llm_raw.py` owns:

- HTTP/SSE transport and retries
- request payload construction for normal chats
- response parsing, token usage, timings, TTFT and throughput metrics
- raw request/response logging
- multi-turn sessions and compaction
- MCP tool clients
- local skills
- human-in-the-loop tool approval
- security policy and redaction
- interactive terminal usage

The split lets the same runner be reused for coding, research, agent experiments, and future evaluation suites without dragging test-specific concepts along.

---

## 2. Goals and non-goals

### Goals

1. **Portable** — copy `llm_raw.py` and `llm_raw.yaml` into another project and run it. No imports from this skill, no required third-party packages.
2. **Raw and observable** — log the exact request and the parsed response, including content, reasoning, tool calls, usage, timings, and optional SSE events.
3. **Multi-purpose** — one-shot prompts, streaming chats, tool-enabled sessions, and a terminal UI.
4. **Safe by default** — tool approval, deny lists, result truncation, redaction, and untrusted-output labeling.
5. **Context-aware** — automatic compaction with a deterministic fallback.
6. **Test-harness friendly** — a stable return contract that `eval_llm.py` can consume without importing test logic into the runner.

### Non-goals for v0.1

- A full-screen curses/textual TUI.
- A complete MCP implementation of prompts, resources, sampling, roots, OAuth, or server-initiated requests.
- A filesystem or shell tool sandbox. MCP servers run with the user's privileges.
- A tokenizer-accurate context counter (uses a character heuristic and server usage).
- Multi-model routing or load balancing.
- Image/audio output.

---

## 3. Design principles

- **One Python file** for the runner; one YAML file for defaults.
- **Standard library first.** Optional PyYAML is detected; a small YAML subset parser is the fallback.
- **Separation of concerns.** `eval_llm.py` may depend on `llm_raw.py`; `llm_raw.py` never imports `eval_llm.py`.
- **No hidden state.** Every request/response and tool decision can be logged to JSONL.
- **Fail visibly.** Connection, protocol, config, and tool errors are surfaced with context; retries are explicit.
- **No silent tool execution.** The default HIL mode is `ask`; non-interactive runs must use `--yes` or a matching auto-approve rule.
- **Tool output is untrusted.** Results are wrapped and the system prompt says not to follow instructions inside them.
- **Conservative secrets handling.** API keys come from env by default, are never logged, and logs are redacted.

---

## 4. Files and layout

```text
.agents/skills/llm-eval/scripts/
├── llm_raw.py        # standalone harness
├── llm_raw.yaml      # defaults
├── eval_llm.py       # testing features; imports llm_raw
└── ...
```

`llm_raw.py` resolves its default config as `llm_raw.yaml` next to itself. `--config` overrides it.

For a new project, copy both files; no package installation is required.

---

## 5. CLI contract

```text
python llm_raw.py [options]
```

### Primary modes

| Mode | Command | Behavior |
|---|---|---|
| Discover | `--discover` | Print model/server summary and exit |
| One-shot | `--prompt "..."` | Send one user message and print the final answer |
| Stdin | `--stdin` | Read the prompt from stdin |
| Interactive | `--chat` | Start the line-oriented terminal UI |
| Skills | `--list-skills` | List discovered skills |
| Tools | `--list-tools` | List registered skills/MCP tools |

If no mode is given and stdin is a TTY, the TUI starts. Otherwise the CLI asks for `--prompt`, `--stdin`, or `--chat`.

### Important options

| Option | Meaning |
|---|---|
| `--config PATH` | YAML defaults |
| `--base-url URL` | Endpoint root or `/v1` URL |
| `--model ID` | Model override |
| `--api-key KEY` | Bearer token; prefer `api_key_env` |
| `--timeout SEC` | Request timeout |
| `--max-retries N` | Retry count for 429/5xx/connection errors |
| `--system TEXT` | Override the system prompt |
| `--skill ID` | Activate a local skill (repeatable) |
| `--skills PATH` | Add a skill search path (repeatable) |
| `--tools/--no-tools` | Enable or disable tool registration |
| `--yes` | Auto-approve tool calls |
| `--stream/--no-stream` | Toggle streaming |
| `--temperature`, `--top-p`, `--max-tokens`, `--seed` | Generation overrides |
| `--max-steps N` | Maximum assistant/tool turns per user message |
| `--no-compact` | Disable context compaction |
| `--log-dir DIR` | JSONL log directory |
| `--no-log` | Disable logging |
| `--raw-sse` | Include raw SSE events in logs |
| `--extra-body JSON` | Advanced request fields |
| `--strict-openai` | Omit llama.cpp/vLLM extensions |
| `--json` | Print the one-shot result as JSON |
| `--no-color` | Disable ANSI color in the TUI |

Exit codes: `0` success, `2` configuration/protocol error, `130` interrupt.

---

## 6. Configuration

`llm_raw.yaml` is merged over built-in defaults. `--` options override the file.

```yaml
endpoint:
  base_url: http://127.0.0.1:8080/v1
  model: null
  api_key_env: LLM_API_KEY
  timeout: 600
  max_retries: 2
  strict_openai: false
  headers: {}
  extra_body: {}

generation:
  temperature: 0.2
  top_p: 0.95
  max_tokens: 1024
  seed: 42

stream: true
max_steps: 8
system_prompt: "You are a capable assistant..."

compaction:
  enabled: true
  threshold_ratio: 0.8
  keep_recent: 8
  strategy: summarize
  summary_max_tokens: 512

logging:
  directory: ./llm-raw-logs
  enabled: true
  raw_sse: false
  redact: true

security:
  require_tool_approval: true
  allowed_tools: []
  denied_tools: ["shell*", "exec*", "system*"]
  max_tool_calls: 8
  max_tool_result_chars: 20000
  allowed_paths: []
  allow_shell: false
  redact_patterns: ["..."]

hil:
  mode: ask
  timeout_seconds: 120
  auto_approve: ["list_skills", "load_skill"]

mcp:
  servers: {}

skills:
  paths: []
  auto_load: []
  max_chars: 12000

tui:
  show_reasoning: true
  color: true
```

Environment references inside strings support `${NAME}` and `{env:NAME}`.

If PyYAML is installed it is used; otherwise the built-in parser supports mappings, nested mappings, block lists, quoted scalars, booleans, numbers, null, and simple inline `[]`/`{}` lists.

---

## 7. Architecture

| Component | Responsibility |
|---|---|
| `RawClient` | Endpoint URL/auth/model, discovery, `chat()` payload construction, logging |
| `complete_payload()` | Low-level POST/SSE, retries, parsing, metrics; used by `eval_llm.py` |
| `Session` | Message history, system/skills, tool loop, compaction, save/load |
| `ToolRegistry` | Tool specs, execution, policy/approval, result wrapping |
| `MCPManager` | Start/close MCP servers; register namespaced tools |
| `StdioMCPClient` / `HttpMCPClient` | JSON-RPC MCP transport |
| `SkillRegistry` | Scan `SKILL.md`/local Markdown, frontmatter, load by id |
| `ApprovalManager` | `ask`/`auto`/`deny`, auto-approve patterns, interactive callback |
| `SecurityPolicy` | Allow/deny patterns, limits, redaction, result wrapping |
| `Compactor` | Threshold check, summarize older turns, deterministic fallback |
| `EventLogger` | Redacted JSONL events |
| `TerminalUI` | Interactive streaming chat, commands, approval prompts |

---

## 8. Raw transport contract

`RawClient.chat()` builds an OpenAI-compatible payload:

```json
{
  "model": "...",
  "messages": [...],
  "stream": true,
  "stream_options": {"include_usage": true},
  "tools": [...],
  "tool_choice": "auto",
  "temperature": 0.2,
  "top_p": 0.95,
  "max_tokens": 1024,
  "seed": 42
}
```

`extra_body` is deep-merged; critical fields (`model`, `messages`, `stream`) are re-applied so an extension cannot break the request shape. `strict_openai` removes `chat_template_kwargs`, `cache_prompt`, `ignore_eos`, `top_k`, `min_p`, and `repeat_penalty`.

`complete_payload()` returns a stable dictionary:

```json
{
  "id": "...",
  "model": "...",
  "content": "...",
  "reasoning": "...",
  "tool_calls": [
    {"id": "...", "type": "function", "function": {"name": "...", "arguments": "..."}}
  ],
  "finish_reason": "stop",
  "usage": {"prompt_tokens": 0, "completion_tokens": 0},
  "timings": {},
  "metrics": {
    "wall_ms": 0,
    "ttft_ms": 0,
    "first_visible_ms": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "cached_tokens": 0,
    "server_prefill_tps": 0,
    "server_decode_tps": 0,
    "wall_decode_tps": 0,
    "tpot_ms": 0,
    "draft_acceptance": null,
    "streamed": true
  },
  "truncated": false,
  "streamed": true,
  "chunk_count": 0,
  "raw": {"...": "parsed non-streaming response; omitted for streamed calls"}
}
```

This is the contract `eval_llm.py` consumes. The transport retries 408/409/425/429/5xx and connection errors; 4xx protocol errors are not retried. `LLMError` is the public error type.

---

## 9. Session and tool loop

`Session.send(user_text)`:

1. Append the user message.
2. If context exceeds the threshold, compact older messages.
3. Call the model with system messages, active skills, and available tools.
4. Append the assistant message.
5. If there are no tool calls, return.
6. For each tool call:
   - parse JSON arguments;
   - apply security policy;
   - request HIL approval if needed;
   - execute;
   - append a `tool` message with the call id and wrapped result.
7. Repeat until a final answer or `max_steps`.

The session stores messages without system prompts; system prompts, active skills, compaction summary, and the security reminder are composed on demand. Results are wrapped:

```text
<tool_result name="..." error="false" trust="untrusted">
...
</tool_result>
```

---

## 10. MCP support

Configure servers under `mcp.servers`:

```yaml
mcp:
  servers:
    filesystem:
      transport: stdio
      command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "D:/work"]
      env: {}
      trust: false
      timeout: 60
    remote:
      transport: http
      url: http://127.0.0.1:8765/mcp
      headers: {}
      trust: false
```

Lifecycle:

1. Start the server.
2. Send `initialize` with protocol version `2024-11-05`.
3. Send `notifications/initialized`.
4. Call `tools/list` (cursor pagination supported).
5. Register tools as `mcp__<server>__<tool>` (long names are hashed).
6. On `tools/call`, preserve the JSON-RPC result and convert text/resource content for the model.

`StdioMCPClient` uses line-delimited JSON-RPC over the process pipes. `HttpMCPClient` uses JSON or SSE JSON-RPC responses and preserves `Mcp-Session-Id` when supplied.

Not yet implemented: OAuth, server-initiated requests, prompts/resources, sampling, roots, and parallel tool execution.

---

## 11. Skills

Skills are local instruction bundles discovered from `skills.paths`:

- `*.md` at the source root
- `*/SKILL.md`
- nested `**/SKILL.md`

Frontmatter:

```yaml
---
name: my-skill
description: What this skill is for
---
```

The body is loaded on demand. The registry exposes two built-in tools:

- `list_skills` — ids, names, descriptions
- `load_skill` — full `SKILL.md` body by id

`skills.auto_load` activates a skill at session creation. The TUI also supports `/skills`, `/skill <id>`, and `/unskill <id>`.

Skills are trusted local content; tool results are still labeled as untrusted data.

---

## 12. Human-in-the-loop (HIL)

Modes:

- `ask` — prompt for `y` (once), `n` (deny), or `a` (always for this session).
- `auto` — allow after security checks.
- `deny` — refuse all tools.

`hil.auto_approve` is a list of glob patterns. `--yes` forces `auto`. In non-interactive mode, a tool that needs approval and has no callback is denied with a message returned to the model.

Each decision is logged with `allowed`, `reason`, and tool name. The session tracks "always approve" choices for its lifetime.

---

## 13. Security

`SecurityPolicy` provides:

- `allowed_tools` / `denied_tools` glob patterns
- `max_tool_calls` per user turn
- `max_tool_result_chars` truncation
- `allow_shell` (no shell tool is built in; future tools must honor it)
- `allowed_paths` (reserved for future file tools)
- `redact_patterns` applied to logs
- API keys resolved from environment and excluded from logs
- tool results wrapped and labeled trusted/untrusted

This is a **policy layer, not an OS sandbox.** MCP servers run with the user's privileges. Do not enable untrusted MCP servers. A future file/shell tool must enforce `allowed_paths` and `allow_shell`; the current version does not ship those tools.

Prompt-injection handling: the system prompt states that tool output is data, not instructions; tool results are visibly wrapped; the model is expected to ignore embedded instructions. This is mitigation, not a guarantee.

---

## 14. Compaction

- Token estimate: `chars / 4`; actual `prompt_tokens` from the server is used when available.
- Trigger: estimated tokens exceed `context_window * threshold_ratio`.
- Strategy: keep system messages and the most recent `keep_recent` conversation messages; summarize the rest.
- Summary: a separate no-tool LLM call with `summary_max_tokens`; if it fails, a deterministic role/content digest is used.
- The summary is stored on the session and included as a system message.
- Recent history never starts with an orphaned `tool` result; the split moves back to include its assistant call.
- The compaction event is logged.

The context window comes from `RawClient.discover()` when available; otherwise it falls back to 32768.

---

## 15. Logging

When enabled, a session writes JSONL:

```text
llm-raw-logs/20261021-150204-raw.jsonl
```

Events:

- `session_start`
- `user`
- `request` (payload, including messages and tools)
- `response` (content, reasoning, tool calls, usage, timings, metrics)
- `tool_call`
- `tool_result`
- `approval`
- `compaction`
- `mcp_server_started` / `mcp_server_error`

`raw_sse: true` includes raw SSE objects in the response event. Logs are redacted for bearer tokens, API keys, and configured patterns. API keys are not written by default. `--no-log` disables the logger.

---

## 16. TUI

`TerminalUI` is a line-oriented terminal harness with streaming output, reasoning display, tool status, and approval prompts.

Commands:

```text
/help                 show help
/quit                 exit
/reset                clear conversation
/system <text>        replace base system prompt
/model <name>         switch model id
/tools                list registered tools
/skills               list skills
/skill <id>           activate skill
/unskill <id>         deactivate skill
/compact              compact now
/save [path]          save session JSON
/load <path>          load session JSON
/log                  show log path
/config               show redacted effective config
/reasoning on|off     show/hide reasoning
/yes                  auto-approve tools for this session
```

It is intentionally not a full-screen curses application; it works in any terminal, including Windows, without extra dependencies. A full-screen TUI is a future enhancement.

---

## 17. eval_llm.py integration

`eval_llm.py` imports `llm_raw` and delegates the raw transport:

```python
def chat_completion(cfg, payload):
    return llm_raw.complete_payload(
        api_url=cfg.api_url,
        api_key=cfg.api_key,
        payload=payload,
        timeout=cfg.timeout,
        retries=cfg.retries,
    )
```

`eval_llm.py` still owns:

- suite loading and case selection
- quality prompts and `quality.jsonl`
- automatic checks
- performance test definitions and aggregates
- run directory artifacts
- discovery properties for reports
- judge/report inputs

The dependency is one-way. `llm_raw.py` has no knowledge of suites, rubric criteria, `quality.jsonl`, or performance tests.

Future migration: move discovery into `llm_raw` and remove the remaining duplicated discovery code from `eval_llm.py`. Until then, discovery remains in eval to avoid changing report behavior.

---

## 18. Portability

- Python 3.10+; standard library only (PyYAML optional).
- Windows, Linux, macOS.
- Default config is next to the script; `--config` supports any path.
- `llm_raw.py` can be copied without the skill directory.
- `eval_llm.py` requires `llm_raw.py` in the same directory (or on `PYTHONPATH`).
- ANSI colors are disabled with `--no-color`.

---

## 19. Limitations and future work

- Full-screen TUI, history search, and multiline editor.
- MCP OAuth, resources, prompts, sampling, roots, server-initiated requests.
- File/shell tools with a real path sandbox and command allowlist.
- Tokenizer-accurate context accounting.
- Parallel tool calls and streaming tool-call deltas to the UI.
- HIL timeout enforcement (currently only interactive input blocking).
- Richer raw log rotation and size limits.
- Multi-server tool federation and conflict resolution.
- Native OpenAI Responses API support.
- Model capability metadata and automatic tool-schema adaptation.

---

## 20. Acceptance criteria for v0.1

- `--discover` prints model properties for a live llama.cpp endpoint.
- `--prompt` returns content, usage, timings, and metrics.
- `--chat` starts, streams, accepts commands, and exits cleanly.
- `--list-skills` finds a local `SKILL.md`.
- `--list-tools` registers skills and MCP tools.
- Stdio and HTTP MCP initialize, list, and call tools.
- HIL ask/auto/deny paths are observable.
- Security deny/allow and redaction work.
- Compaction produces a summary and keeps the conversation usable.
- Logs are valid JSONL and contain no bearer token.
- `eval_llm.py --plan quality` and `--plan perf` still work through `llm_raw.complete_payload`.
- Both files run with `python -m py_compile`.
