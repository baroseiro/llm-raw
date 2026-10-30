# Publishing checklist

This guide is for maintainers preparing a public release of `llm-raw`.

## 1. Verify the local repository

```bash
uv sync --locked
uv run pytest
uv run python -m py_compile llm_raw.py
uv build
```

Install the wheel into a clean environment and run:

```bash
llm-raw --version
llm-raw --help
llm-raw --list-skills --no-log
```

The version must match `llm_raw.VERSION` and the latest `CHANGELOG.md` entry;
packaging reads the version dynamically from the module.

## 2. Create the GitHub repository

With the GitHub CLI:

```bash
gh repo create baroseiro/llm-raw \
  --public \
  --source=. \
  --remote=origin \
  --push
```

The project uses `master` as its only long-lived branch. The CI workflow runs on
pushes to `master` and on pull requests.

Set the repository description and topics:

```bash
gh repo edit baroseiro/llm-raw \
  --description "A small, transparent harness for OpenAI-compatible LLM endpoints." \
  --add-topic llm \
  --add-topic openai \
  --add-topic openai-compatible \
  --add-topic mcp \
  --add-topic llama-cpp \
  --add-topic vllm \
  --add-topic ollama \
  --add-topic cli
```

## 3. Configure repository security

- Enable **Private vulnerability reporting** under **Settings → Code security**.
- Enable **Dependabot alerts** and **Dependabot security updates**.
- Review the default branch protection rules.
- Confirm that `SECURITY.md` is visible under the **Security** tab.

## 4. Confirm CI

The workflow in `.github/workflows/ci.yml` runs on pushes and pull requests. It
tests Windows and Linux on Python 3.14, compiles the module, runs the offline
suite, and builds the distribution.

The README CI badge points at:

```text
https://github.com/baroseiro/llm-raw/actions/workflows/ci.yml
```

## 5. Tag and release

```bash
git tag v0.2.0
git push --tags
gh release create v0.2.0 \
  --title "llm-raw 0.2.0" \
  --notes-file CHANGELOG.md \
  dist/llm_raw-0.2.0-py3-none-any.whl \
  dist/llm_raw-0.2.0.tar.gz
```

Check that the release contains the wheel and source archive.

## 6. Publish to PyPI (optional)

`llm-raw` is not on PyPI yet. To publish:

1. Create the project on PyPI.
2. Configure a trusted publisher for the GitHub repository, or use an API token.
3. Build and publish:

   ```bash
   uv build
   uv publish
   ```

4. Verify the install in a clean environment:

   ```bash
   pip install llm-raw
   llm-raw --version
   ```

## 7. Post-release checks

- README badges render correctly.
- CI is green on the default branch.
- The release tag matches the version in `llm_raw.py`.
- `pip install` / `uv tool install` works from the published source.
- The issue templates and security advisory link work.
