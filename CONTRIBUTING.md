# Contributing to llm-raw

Thanks for taking the time to contribute. `llm-raw` is intentionally small:
one runtime module, no required dependencies, and an offline test suite. Keeping
those constraints is part of the design, not an accident.

## Ways to contribute

- Report a reproducible bug using the bug report template.
- Propose a focused feature using the feature request template.
- Improve documentation, examples, or error messages.
- Send a pull request with tests for behavior changes.

For security vulnerabilities, do **not** open a public issue. Follow
[`SECURITY.md`](SECURITY.md) instead.

## Development setup

Requirements: Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/baroseiro/llm-raw.git
cd llm-raw
uv sync
uv run llm-raw --help
uv run pytest
```

`uv sync` creates `.venv`, installs the project in editable mode, and installs
the development dependencies.

Optional: install PyYAML to exercise the full YAML parser path.

```bash
uv sync --extra yaml
```

## Repository layout

```text
llm_raw.py                  runtime: transport, sessions, tools, MCP, logging, UI
llm-raw.yaml                optional default configuration
tests/test_llm_raw.py       offline unit and integration tests
docs/SPEC.md                behavioral specification
docs/PLAN.md                delivery plan and scope notes
.github/workflows/ci.yml    CI matrix
pyproject.toml              packaging and command entry point
```

## Running checks

Run these before opening a pull request:

```bash
uv run pytest
uv run python -m py_compile llm_raw.py
uv run llm-raw --version
uv build
```

The test suite is fully offline. It uses a fake OpenAI-compatible HTTP server, a
fake MCP HTTP server, and a fake MCP stdio subprocess. No model, GPU, or API key
is required.

## Design constraints

Please keep changes consistent with the existing project:

- **One runtime module.** Put runtime code in `llm_raw.py`.
- **Standard library first.** Avoid required third-party runtime dependencies.
  Optional integrations must degrade gracefully.
- **Observable behavior.** Requests, responses, tool calls, approvals, and
  compaction events should remain loggable without leaking secrets.
- **Fail closed.** Tool execution requires approval by default; unattended runs
  deny unless the user explicitly opts in.
- **Stable result contract.** Preserve the result-dictionary keys documented in
  `docs/SPEC.md`.
- **Cross-platform.** Test on Windows and Linux; avoid shell-specific assumptions.
- **Offline tests.** New tests must not call real model endpoints or require
  network access.

## Making a change

1. Fork the repository and create a focused branch.
2. Add or update tests for behavior changes.
3. Update `README.md`, `docs/SPEC.md`, or `CHANGELOG.md` when the change is
   user-visible.
4. Run the checks above.
5. Open a pull request with a short summary and the commands you ran.

Small, focused pull requests are easier to review than large mixed changes. If a
change affects the security model, the result contract, or packaging, explain
the reasoning in the pull request.

## Commit messages

There is no enforced commit format, but short imperative messages are preferred:

```text
transport: retry 429 responses
docs: clarify one-shot streaming behavior
test: cover MCP pagination
```

## Code style

The project has no formatter or linter dependency. Match the surrounding style:
type hints on public functions, docstrings for non-obvious behavior, and small
helpers over clever abstractions.

## Reporting bugs

Use the bug report template and include:

- `llm-raw --version`
- operating system and Python version
- endpoint or provider type (llama.cpp, vLLM, LM Studio, Ollama, hosted API)
- the exact command or Python snippet
- expected and actual behavior
- relevant redacted logs or tracebacks

**Never paste API keys, bearer tokens, or private prompts.** Redact logs before
attaching them.

## Code of conduct

By participating, you agree to follow the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
