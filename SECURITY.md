# Security policy

## Supported versions

| Version | Supported |
|---|---|
| `0.2.x` | Yes |
| `< 0.2` | No |

Security fixes are applied to the latest released version.

## Reporting a vulnerability

Please report security issues privately using GitHub's private vulnerability
reporting:

**https://github.com/baroseiro/llm-raw/security/advisories/new**

Do **not** open a public issue for a vulnerability. Include:

- affected version (`llm-raw --version`)
- operating system and Python version
- a description of the issue and its impact
- a minimal reproduction or proof of concept
- any suggested fix or mitigation

This is a volunteer project. Reports will be acknowledged as soon as possible,
and a remediation timeline will be agreed based on severity and complexity.

## Scope

In scope:

- bypassing tool approval or the security policy
- leaking API keys, bearer tokens, or other secrets into logs
- unsafe handling of tool results or prompt-injection defenses
- command injection or argument handling issues in MCP transports
- denial of service caused by malformed endpoint or MCP responses
- packaging or installation issues that execute unintended code

Out of scope:

- vulnerabilities in third-party MCP servers or model providers
- prompt injection that only changes model text output
- risks from deliberately unsafe configuration (`--yes`, `hil.mode: auto`,
  `trust: true`, connecting an untrusted MCP server)
- security of the local endpoint, model weights, or host operating system
- missing hardening that requires an OS-level sandbox

## Security model

`llm-raw` is a **policy layer, not an operating-system sandbox**.

- Tool calls require approval by default (`hil.mode: ask`).
- Unattended runs deny tools that need approval unless the user opts in.
- Dangerous tool names are denied by default (`shell*`, `exec*`, `system*`).
- Tool results are truncated, labeled, and treated as untrusted data.
- Logs redact known secret patterns and the active API key.

MCP servers run with your user privileges and can do anything you can do. Do not
connect MCP servers you do not trust. Prompt-injection defenses in the harness
are mitigations, not guarantees.

See the [security model](README.md#security-model) in the README for the full
description.

## Safe harbor

Good-faith security research is welcome. If you make a reasonable effort to avoid
privacy violations, service disruption, and data loss while investigating, the
maintainer will not pursue legal action or report you to platform operators.
Please give reasonable time to fix the issue before public disclosure.
