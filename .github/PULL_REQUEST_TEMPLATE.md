## Summary

<!-- Describe the change in 1–3 sentences. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Packaging / CI
- [ ] Refactor (no behavior change)
- [ ] Security hardening

## Related issues

<!-- Link issues, for example: Closes #123 -->

## Testing

<!-- List the commands you ran and any manual checks. -->

- [ ] `uv run pytest`
- [ ] `uv run python -m py_compile llm_raw.py`
- [ ] `uv build`
- [ ] Manual check against an OpenAI-compatible endpoint (describe below)

## Checklist

- [ ] Tests cover the behavior change
- [ ] User-visible changes are documented in `README.md`, `docs/SPEC.md`, or
      `CHANGELOG.md`
- [ ] No API keys, tokens, prompts, or other secrets are included in this PR
- [ ] The result-dictionary contract in `docs/SPEC.md` is unchanged, or the
      change is documented
- [ ] Runtime code remains in `llm_raw.py` and required dependencies remain at
      zero where possible
