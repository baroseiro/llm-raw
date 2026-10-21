# llm-raw — Implementation and Delivery Plan

Companion: [`SPEC.md`](SPEC.md)
Baseline commit: `chore: import existing llm_raw harness baseline`

This plan re-initializes the folder as a standalone UV Python project and
carries the existing single-file harness across with minimal structural change.
The runtime stays in **one Python module**, `llm_raw.py`; the project, command,
and documentation use the product name **`llm-raw`**.

The underscore in `llm_raw.py` is intentional: Python import names cannot
contain hyphens, and a normal importable module is required for the console
entry point, tests, and the public Python API. The installed command is
`llm-raw` and the distribution name is `llm-raw`.

---

## 1. Starting point

The imported baseline contains:

- `llm_raw.py` — 2,381-line single-file harness
- `llm_raw.yaml` — defaults with a syntax error in the `security` block
- `SPEC_LLM_RAW.md`, `PLAN_LLM_RAW.md` — legacy docs that reference an
  external host project and its evaluation suite
- no Git history, packaging, tests, README, license, or CI

Initial audit findings:

| Area | Finding | Action |
|---|---|---|
| Identity | Docstring refers to an external skill host and an evaluation script | Remove all references; describe only `llm-raw` |
| Naming | `llm_raw` used as product name | Product name `llm-raw`; keep `llm_raw` only as module/import name |
| Packaging | No `pyproject.toml` | Add UV-managed setuptools project |
| Config | `llm_raw.yaml`; default only next to the module; invalid YAML in `security` | Rename, add discovery order, fix YAML |
| Skills | Optional local instruction packs are a harness feature | Keep feature, clarify it is not the app's packaging format |
| Tests | None | Add offline unit/integration suite |
| Docs | Legacy docs reference the old host project | Replace with `docs/SPEC.md`, `docs/PLAN.md`, `README.md` |
| Publication | No README, license, gitignore, or CI | Add publication-ready repository files |

The YAML file currently contains:

```yaml
  redact_patterns: ["..."]
```

That inline `["..."]` value is not valid YAML (unquoted inner quotes) and the
built-in parser does not parse it. It will be replaced with a valid block list.

---

## 2. Target layout

```text
llm-raw/
├── .github/workflows/ci.yml
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml
├── uv.lock
├── llm-raw.yaml
├── llm_raw.py
├── tests/
│   └── test_llm_raw.py
└── docs/
    ├── SPEC.md
    └── PLAN.md
```

No `src/` split and no package directory. The single-module layout is a product
constraint: it keeps the harness copyable and auditable.

---

## 3. Phase plan

### Phase 0 — baseline and documentation (done)

Deliverables:

- [x] `git init` and baseline commit before any edits
- [x] `docs/SPEC.md` rewritten as a standalone `llm-raw` specification
- [x] `docs/PLAN.md` (this document)

Commit:

```text
docs: add llm-raw specification and migration plan
```

Acceptance:

- Baseline commit contains the imported files unchanged.
- Spec contains no references to external projects.
- Plan lists every commit checkpoint used during delivery.

### Phase 1 — UV project and identity (milestone: installable app)

Tasks:

- [ ] Add `pyproject.toml`:
  - distribution `llm-raw`, version `0.2.0`
  - `requires-python = ">=3.10"`
  - setuptools backend with `py-modules = ["llm_raw"]`
  - console script `llm-raw = "llm_raw:main"`
  - optional `yaml` extra, `dev` dependency group with pytest
- [ ] Run `uv lock` and `uv sync`
- [ ] Rename `llm_raw.yaml` → `llm-raw.yaml`
- [ ] Fix invalid YAML in `security.redact_patterns`
- [ ] Update module identity:
  - docstring and version
  - `DEFAULT_CONFIG` / config discovery
  - MCP `clientInfo` name
  - TUI banner and argparse program name
  - save/session/log filenames where needed
- [ ] Add `LLM_RAW_CONFIG` and current-directory config discovery
- [ ] Remove legacy `SPEC_LLM_RAW.md` and `PLAN_LLM_RAW.md`
- [ ] Add `.gitignore` for UV/Python/logs/sessions
- [ ] Add MIT `LICENSE`
- [ ] Verify `python -m py_compile llm_raw.py`, `uv run llm-raw --help`,
  `uv run llm-raw --version`, and `uv run llm-raw --list-skills`

Commit:

```text
feat: reinitialize llm-raw as a standalone uv project
```

Acceptance:

- `uv sync` completes.
- `uv run llm-raw --help` shows `llm-raw`.
- Importing `llm_raw` has no side effects.
- No string in the repository references external projects.
- The app runs with no config file using built-in defaults.

### Phase 2 — offline tests and runtime hardening (milestone: verified core)

Tasks:

- [ ] Add `tests/test_llm_raw.py` covering:
  - YAML subset parser and the shipped `llm-raw.yaml`
  - environment expansion
  - URL normalization and headers
  - SSE parsing: content, reasoning, tool-call deltas, usage, timings,
    `[DONE]`, keep-alive
  - non-streaming parsing
  - retry policy: retry 429/5xx/connection errors, not 400
  - metrics: TTFT, throughput, estimated tokens, missing server timings
  - redaction of bearer/API keys and configured patterns
  - security allow/deny patterns and result truncation
  - approval modes `ask`/`auto`/`deny`, auto-approve patterns, non-interactive
    denial, `always`
  - tool name namespacing and hashing
  - skill scanning, frontmatter, load-by-id
  - compaction: threshold, system preservation, tool-pair boundary, fallback
  - session save/load
  - CLI smoke tests using `python -m`/`main` for `--version`, `--help`,
    `--list-skills`, and `--list-tools`
  - fake MCP stdio client exchange
- [ ] Add a local fake HTTP endpoint for streaming/non-streaming transport tests
  (standard library only)
- [ ] Fix defects found by the tests
- [ ] Ensure all tests run offline and on Windows

Commit:

```text
test: add offline coverage for transport, tools, and sessions
```

Acceptance:

- `uv run pytest` passes with no network access.
- No test writes outside a temporary directory.
- No runtime dependency beyond the standard library is required.

### Phase 3 — publication files (milestone: repository ready)

Tasks:

- [ ] Write `README.md`:
  - what the harness is and why it exists
  - feature matrix
  - install with UV and pip
  - quick start against a local OpenAI-compatible server
  - one-shot, stdin, and interactive examples
  - configuration reference and discovery order
  - MCP configuration example
  - local instruction-pack example
  - security model and limitations
  - logging and metrics explanation
  - Python API example
  - development, testing, and release instructions
  - license
- [ ] Add GitHub Actions CI:
  - `uv sync --locked`
  - `uv run pytest`
  - `uv build`
  - matrix over Python 3.10 and 3.12
- [ ] Add repository metadata polish: description, topics, and release checklist
  in `README.md`

Commit:

```text
docs: add publication-ready readme
```

Follow-up commit if CI is added separately:

```text
ci: validate tests and builds with github actions
```

Acceptance:

- README commands work from a clean clone.
- README contains no references to external projects.
- CI workflow is valid and runs offline tests.

### Phase 4 — packaging and release verification (milestone: shippable)

Tasks:

- [ ] `uv build` produces wheel and sdist
- [ ] Install the wheel into a temporary virtual environment and run:
  - `llm-raw --version`
  - `llm-raw --help`
  - `llm-raw --list-skills`
- [ ] Confirm the wheel contains `llm_raw.py` and metadata
- [ ] Run the app from a different working directory with:
  - no config
  - `--config` pointing at the example
  - `LLM_RAW_CONFIG`
- [ ] Verify JSONL logging and redaction with a fake endpoint
- [ ] Final `git status` is clean and the log contains the planned commits

Commit (only if fixes are needed):

```text
fix: address packaging and release verification findings
```

Optional tag after all checks:

```text
v0.2.0
```

Acceptance:

- `uv run pytest`, `uv build`, and wheel smoke tests pass.
- `llm-raw --version` prints `llm-raw 0.2.0`.
- Repository is clean and ready to push.

---

## 4. Commit checkpoints

| Commit | Phase | Purpose |
|---|---|---|
| `chore: import existing llm_raw harness baseline` | 0 | untouched import |
| `docs: add llm-raw specification and migration plan` | 0 | spec + plan |
| `feat: reinitialize llm-raw as a standalone uv project` | 1 | packaging + rename |
| `test: add offline coverage for transport, tools, and sessions` | 2 | tests + fixes |
| `docs: add publication-ready readme` | 3 | README |
| `ci: validate tests and builds with github actions` | 3 | CI |
| `fix: address packaging and release verification findings` | 4 | only if needed |

Each commit must leave the tree runnable and `python -m py_compile llm_raw.py`
passing.

---

## 5. Verification matrix

| Check | Command | Phase |
|---|---|---|
| Syntax | `python -m py_compile llm_raw.py` | 1 |
| Environment | `uv sync` | 1 |
| CLI help | `uv run llm-raw --help` | 1 |
| Version | `uv run llm-raw --version` | 1 |
| No actions | `uv run llm-raw --list-skills` | 1 |
| Unit/integration | `uv run pytest` | 2 |
| Distribution | `uv build` | 4 |
| Installed wheel | `llm-raw --version` in a temp venv | 4 |
| Logging | fake endpoint + JSONL inspection | 2/4 |
| Secret redaction | unit tests + JSONL inspection | 2/4 |

Network-dependent checks (`--discover`, live `--prompt`) are manual because CI
must stay deterministic. They are not release blockers when no endpoint is
available.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Hyphenated project name cannot be imported | Distribution/command `llm-raw`; module `llm_raw`; document the split |
| Config rename breaks existing users | New discovery order plus `--config`; built-in defaults always work |
| Legacy docs keep old references alive | Delete legacy docs in Phase 1; add a repository-wide grep check |
| Moving code breaks the console script | Entry point resolves `llm_raw:main`; test installed wheel |
| YAML fallback diverges from PyYAML | Test the shipped config through both parsers when PyYAML is present |
| Test suite couples to a live model | Fake HTTP/SSE endpoint and fake MCP stdio server only |
| Accidental secret in logs | Redaction tests plus no auth-header logging |
| Scope creep into multiple modules | One-file rule enforced by review; only tests/docs are separate |
| Windows subprocess/encoding issues | Explicit UTF-8 configuration and Windows test run |

---

## 7. Non-goals for this migration

- Rewriting the transport or session architecture.
- Adding new tool types, sandboxes, or MCP capabilities.
- A full-screen TUI.
- Changing the result dictionary shape.
- Moving evaluation, quality, or reporting features into `llm-raw`. Those
  belong to other projects and are out of scope.

---

## 8. Definition of done

- The folder is a valid UV project with a lockfile.
- `llm-raw` installs as a console command and runs from any directory.
- Runtime code remains one file: `llm_raw.py`.
- Optional YAML config is `llm-raw.yaml`; built-in defaults work without it.
- All tests are offline, deterministic, and passing.
- README is publication-ready for GitHub.
- Legacy docs and all host-project references are gone.
- SPEC and PLAN match the delivered behavior.
- Planned commits exist in Git history.

