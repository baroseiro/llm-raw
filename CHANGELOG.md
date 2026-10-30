# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-30

### Added

- Standalone `llm-raw` command and importable `llm_raw` module.
- OpenAI-compatible streaming and non-streaming chat with reasoning-content
  support.
- One-shot, stdin, and interactive terminal modes.
- Multi-turn sessions with tool loops and automatic context compaction.
- MCP tool clients over stdio and HTTP JSON-RPC, including SSE responses.
- Human-in-the-loop tool approval with `ask`, `auto`, and `deny` modes.
- Security policy with allow/deny patterns, call limits, result truncation,
  trust labels, and secret redaction.
- JSONL logging for requests, responses, tool calls, approvals, compaction, and
  MCP lifecycle events.
- Local Markdown instruction packs with `list_skills` and `load_skill` tools.
- Endpoint discovery for llama.cpp-style metadata and `/v1/models`.
- Optional `PyYAML` extra and a built-in YAML subset parser.
- Offline test suite with fake OpenAI-compatible and MCP servers.
- GitHub Actions CI for Windows and Linux on Python 3.14.
- Contributor, security, changelog, and publishing documentation, plus GitHub
  issue/PR templates and Dependabot configuration.

### Changed

- Repackaged the original single-file harness as a uv-managed Python project.
- Product and command name is `llm-raw`; the import module is `llm_raw`.
- Removed references to the legacy host project and evaluation suite.
- `--skills` now appends search paths instead of replacing configured paths.

### Security

- API keys are read from the environment and redacted from logs.
- Tool results are labeled as trusted or untrusted and truncated at a
  configurable limit.
- Unattended runs deny tool calls that require approval.

[Unreleased]: https://github.com/baroseiro/llm-raw/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/baroseiro/llm-raw/releases/tag/v0.2.0
