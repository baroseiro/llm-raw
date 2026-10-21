# PLAN_LLM_RAW.md

Implementation plan for `llm_raw.py` and its integration with `eval_llm.py`.

Status: **Phase 0–5 baseline implemented**; Phase 6 hardening remains.  
Companion spec: `SPEC_LLM_RAW.md`.

---

## 1. Current state (v0.1.0)

Implemented:

- [x] Single-file `llm_raw.py` + `llm_raw.yaml`
- [x] OpenAI-compatible streaming and non-streaming chat
- [x] Retries for 429/5xx/connection errors; no retry for normal 4xx
- [x] TTFT, prefill/decode throughput, wall metrics, usage/timings
- [x] JSONL request/response logging with redaction
- [x] Multi-turn `Session` with system prompts and active skills
- [x] Context compaction with model summary and deterministic fallback
- [x] Local skill discovery and `list_skills` / `load_skill`
- [x] MCP stdio client and HTTP JSON/SSE client
- [x] Tool registry with namespaced MCP tools
- [x] HIL approval (`ask`, `auto`, `deny`; `y/n/a`)
- [x] Security allow/deny patterns, max tool calls, result truncation, redaction
- [x] Line-oriented TUI with streaming, commands, approval prompts, save/load
- [x] `eval_llm.py` delegates chat transport to `llm_raw.complete_payload`
- [x] Live smoke tests against the local llama.cpp/Strata endpoint
- [x] MCP stdio and HTTP smoke tests with temporary servers
- [x] Quality and performance smoke tests through the refactored eval harness

Not yet done:

- [ ] Full-screen TUI
- [ ] MCP OAuth/resources/prompts/sampling/roots
- [ ] File/shell tools with a real sandbox
- [ ] Tokenizer-accurate context accounting
- [ ] Parallel tool execution
- [ ] HIL timeout enforcement
- [ ] Move eval discovery fully into `llm_raw`
- [ ] Automated regression test suite checked into the repo

---

## 2. Phase plan

### Phase 0 — contracts and defaults (done)

Deliverables:

- `SPEC_LLM_RAW.md`
- `PLAN_LLM_RAW.md`
- `llm_raw.yaml`
- decision: single-file runner, one-way dependency from eval

Acceptance:

- Spec reviewed; config defaults load.
- No unrelated changes to suite files.

### Phase 1 — raw transport (done)

Tasks:

- [x] URL normalization (`root` vs `/v1`)
- [x] API key from env or CLI
- [x] streaming SSE parser with reasoning, content, tool-call deltas
- [x] non-stream fallback
- [x] usage/timings metrics
- [x] retry policy
- [x] strict OpenAI mode
- [x] discovery of `/props`, `/v1/models`, `/health`, `/slots`
- [x] JSONL logger with redaction

Acceptance:

- One-shot prompt returns a stable result dictionary.
- Metrics match server timings.
- `eval_llm.py` quality/perf paths pass smoke tests.

### Phase 2 — sessions, skills, MCP (done baseline)

Tasks:

- [x] `Session.send` tool loop
- [x] system prompt composition
- [x] skills scanner/frontmatter
- [x] `list_skills`, `load_skill`
- [x] MCP stdio transport
- [x] MCP HTTP JSON/SSE transport
- [x] MCP initialize/list/call
- [x] namespaced tool names
- [x] tool result conversion

Acceptance:

- Local `SKILL.md` is listed and loadable.
- Temporary stdio/HTTP MCP server tools are listed and callable.
- Tool loop returns a final answer after a tool result.

### Phase 3 — HIL and security (done baseline)

Tasks:

- [x] `ask` / `auto` / `deny` modes
- [x] auto-approve glob patterns
- [x] `--yes`
- [x] deny by default in non-interactive mode when approval is required
- [x] per-session "always approve"
- [x] max tool calls per user turn
- [x] max tool result size
- [x] redaction patterns
- [x] untrusted tool result wrapper
- [x] log approval decisions

Acceptance:

- Denied tools return a denial to the model, not a crash.
- Logs contain no API key or bearer token.
- `shell*`/`exec*` are denied by default.

### Phase 4 — TUI (done v1)

Tasks:

- [x] banner/help
- [x] streaming content and reasoning
- [x] tool-call and tool-result status
- [x] approval prompt `y/n/a`
- [x] `/reset`, `/system`, `/model`, `/tools`, `/skills`, `/skill`, `/unskill`
- [x] `/compact`, `/save`, `/load`, `/log`, `/config`, `/reasoning`, `/yes`
- [x] `--no-color`
- [x] Ctrl+C/EOF handling at prompt

Future full-screen TUI is a separate phase; the current line-oriented UI is the supported v1.

### Phase 5 — eval integration (done baseline)

Tasks:

- [x] import `llm_raw` in `eval_llm.py`
- [x] replace low-level `_stream_chat`/`chat_completion` with `llm_raw.complete_payload`
- [x] keep quality/performance/report logic in `eval_llm`
- [x] preserve result keys used by checks and reports
- [x] smoke-test quality and performance

Remaining:

- [ ] Move eval's duplicate discovery code to `llm_raw.RawClient.discover`
- [ ] Remove duplicate low-level constants/imports from eval
- [ ] Add a compatibility test that asserts the returned metric keys

### Phase 6 — hardening (next)

Priority order:

1. **Regression tests**
   - Unit tests for YAML fallback, SSE parser, retries, redaction, compaction.
   - Fake-client session tests for tool approval and tool loops.
   - Temporary MCP stdio/HTTP servers in tests.
2. **Context safety**
   - Tokenizer option (tiktoken/HF) with a stdlib fallback.
   - Better summary budget and tool-pair preservation.
3. **Security**
   - HIL timeout implementation.
   - Path-sandboxed file tools and shell allowlist (separate opt-in).
   - Log rotation and max log file size.
4. **MCP completeness**
   - OAuth, resources, prompts, sampling, roots, server-initiated requests.
   - Parallel tool calls.
5. **TUI**
   - Full-screen option, history, multiline editor, search.
6. **Eval cleanup**
   - Shared discovery and a single transport contract test.

---

## 3. Test plan

### Unit / offline

- YAML fallback parses `llm_raw.yaml` identically to PyYAML.
- SSE parser handles content, reasoning, tool calls, usage, timings, `[DONE]`, keep-alive.
- Retry policy retries 429/5xx and connection errors; does not retry 400.
- Metrics return nulls when server timings are absent.
- Redaction removes bearer/API-key patterns and exact secrets.
- Compaction keeps system messages, summary, and tool-pair boundaries.
- Approval modes allow/deny as specified.
- Tool names are namespaced and length-safe.
- Skill frontmatter parser handles quoted descriptions.

### Integration / local

- `--discover` against a live llama.cpp/Strata endpoint.
- One-shot streaming and non-streaming.
- TUI `/help`, `/tools`, `/skills`, `/quit`.
- MCP stdio echo server: list + call.
- MCP HTTP echo server: list + call.
- Log file JSONL validity and redaction.
- `eval_llm.py --plan quality --cases ...` and `--plan perf` through the raw transport.

### Manual / acceptance

- HIL: approve, deny, always approve.
- A model that emits a tool call receives the tool result and finishes.
- A denied tool does not crash; the model gets `DENIED: ...`.
- A long conversation compacts and continues.
- Save/load a session and resume it.

### Regression gate

Every phase must keep:

```bash
python -m py_compile llm_raw.py eval_llm.py
python llm_raw.py --discover
python eval_llm.py --validate-suite --suite-version 1
python eval_llm.py --validate-suite --suite-version 2
```

and a small quality/perf smoke run.

---

## 4. eval_llm migration details

Current:

```python
import llm_raw

def chat_completion(cfg, payload):
    return llm_raw.complete_payload(
        api_url=cfg.api_url,
        api_key=cfg.api_key,
        payload=payload,
        timeout=cfg.timeout,
        retries=cfg.retries,
    )
```

Preserve these result keys:

- `id`, `model`
- `content`, `reasoning`, `tool_calls`
- `finish_reason`, `usage`, `timings`
- `metrics` with `wall_ms`, `ttft_ms`, `prompt_tokens`, `completion_tokens`, `server_prefill_tps`, `server_decode_tps`, `wall_decode_tps`, `tpot_ms`
- `truncated`, `streamed`

Do not move suite/rubric/check/performance logic into `llm_raw`.

### Discovery migration (future)

Target:

```python
client = llm_raw.RawClient(base_url=..., api_key=..., model=...)
discovered = client.discover(include_metrics=...)
```

Eval should map `llm_raw`'s summary to its current run metadata shape. Add a contract test before removing eval discovery.

---

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Duplicate transport code drifts | Final migration removes eval's low-level parser; contract test |
| MCP server hangs | per-request timeouts; close/terminate; reader threads |
| Prompt injection via tool output | untrusted wrapper, system warning, HIL, deny lists |
| Secret leakage in logs | env-only defaults, redaction, no auth headers, log tests |
| Context overflow | compaction threshold, summary fallback, server usage |
| TUI blocks on approval | explicit ask/auto/deny; non-interactive default deny |
| Large tool results | truncation limit and visible marker |
| YAML parser limitations | PyYAML optional; fallback tested against config |
| Windows subprocess quoting | command lists preferred; string fallback via shlex |

---

## 6. Definition of done for v0.1

- `llm_raw.py` and `llm_raw.yaml` run independently in a new directory.
- One-shot, TUI, discovery, skills, MCP stdio/HTTP, HIL, security, compaction, and logging all have smoke evidence.
- `eval_llm.py` uses `llm_raw.complete_payload` for chat and still passes quality/performance smoke tests.
- `SPEC_LLM_RAW.md` and this plan describe the contract and remaining work.
- No suite rubric or report behavior is changed by the refactor.
