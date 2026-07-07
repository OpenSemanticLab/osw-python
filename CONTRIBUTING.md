# Contributing

Contributions are welcome! You can help by reporting bugs, implementing
features, or improving documentation. File issues and PRs at
[github.com/OpenSemanticLab/osw-python](https://github.com/OpenSemanticLab/osw-python).

## Development Setup

Requires `uv` and `git`.

```bash
git clone git@github.com:YOUR_NAME/osw-python.git
cd osw-python
```

With `make`:

```bash
make install
```

Without `make`:

```bash
uv sync
uv run pre-commit install
```

## Making Changes

1. Create a branch: `git checkout -b name-of-your-fix`
2. Make your changes and add tests in `tests/`
3. Run checks and tests (see below)
4. Commit and push, then open a pull request

### Checks and tests

With `make`:

```bash
make check   # lint, type-check, dependency audit
make test    # pytest with coverage
```

Without `make`:

```bash
uv lock --locked
uv run pre-commit run -a
uv run ty check
uv run deptry src
uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml
```

Integration tests need credentials for a test wiki and are excluded by
default:

```bash
uv run pytest tests/integration -o addopts="" --wiki_domain "<domain>" --wiki_username "<login>" --wiki_password "<password>"
```

### Docs

With `make`:

```bash
make docs        # serve with live reload at http://localhost:8000
make docs-test   # strict build, fails on any warning
```

Without `make`:

```bash
uv run zensical serve
uv run zensical build -s
```

## Releasing

Releases are published automatically by CI when a version tag is pushed.

1. Ensure all changes are merged to `main`
2. Tag the commit and push:

   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```

CI will build the package (`uv build`), publish it to PyPI via trusted
publishing, and deploy the versioned docs to GitHub Pages. The version is
derived from the git tag via `hatch-vcs`, so no manual version bumping is
needed.

## AI Guidelines

We believe that AI, and in particular LLMs, can be helpful conventional
tools to accelerate development and improve quality when used responsibly.
AI or any other tool is never the author of code; a human developer always
is. Therefore, it is mandatory to carefully review all generated content
for correctness, quality, and the absence of legal and ethical issues. For
consistency, please avoid patterns that are hard to maintain manually, such
as duplicated content or special characters like em dashes or UTF icons.
