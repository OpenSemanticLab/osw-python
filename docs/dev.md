<!-- markdownlint-disable MD046 -- fenced blocks inside content tabs are indented by design -->

# Development

Everything you need to work on osw-python. Each step comes as a `make`
one-liner or as the underlying commands, pick your style with the tabs.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and `git`.

=== "make"

    ```bash
    make install
    ```

=== "manual"

    ```bash
    uv sync
    uv run pre-commit install
    ```

## Quality checks

Lock consistency, linting and formatting (pre-commit incl. ruff), static
type checking (ty) and dependency audit (deptry) in one go:

=== "make"

    ```bash
    make check
    ```

=== "manual"

    ```bash
    uv lock --locked
    uv run pre-commit run -a
    uv run ty check
    uv run deptry src
    ```

## Testing

Add new tests as `test_*.py` under `tests/`. Integration tests are
excluded by default:

=== "make"

    ```bash
    make test
    ```

=== "manual"

    ```bash
    uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml
    ```

### Integration tests

Integration tests run against a live wiki and need credentials; tests
whose credentials are missing skip instead of fail. CI runs them on
every push to `main` (workflow `integration.yml`).

=== "make"

    ```bash
    WIKI_DOMAIN="<domain>" WIKI_USERNAME="<login>" WIKI_PASSWORD="<password>" \
        make test-integration
    ```

=== "manual"

    ```bash
    uv run pytest tests/integration -o addopts="" \
        --wiki_domain "<domain>" \
        --wiki_username "<login>" \
        --wiki_password "<password>"
    ```

## Documentation

Serve locally with live reload at `http://localhost:8000`, or run the
strict build that fails on any warning:

=== "make"

    ```bash
    make docs        # serve with live reload
    make docs-test   # strict build
    ```

=== "manual"

    ```bash
    uv run zensical serve
    uv run zensical build -s
    ```

## Building

=== "make"

    ```bash
    make build
    ```

=== "manual"

    ```bash
    uv build
    ```

## Releasing

Maintainers release by pushing a version tag; CI builds the package,
publishes it to PyPI via trusted publishing and deploys the versioned
docs. The version is derived from the tag by `hatch-vcs`, no manual
bumping needed:

```bash
git tag v1.2.0 && git push origin v1.2.0
```
