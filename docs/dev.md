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

`pre-commit install` wires both hook stages (`pre-commit` and `commit-msg`);
the latter enforces the commit message format below.

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
whose credentials are missing skip instead of fail. CI runs them on every
pull request into `main` (workflow `integration.yml`), so they gate the
release rather than run after it.

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

### Credentials

Credentials are never written to disk automatically. For a single instance,
set `OSW_USERNAME` / `OSW_PASSWORD` (e.g. via a `.env` file) or answer the
interactive prompt; both are kept in memory only.

For transfers between several OpenSemanticLab instances, keep a hand-maintained
`accounts.pwd.yaml` at the project root (read only, gitignored by default), with
one entry per instance IRI:

```yaml
https://wiki-a.example.org:
  username: <login>
  password: <password>
https://wiki-b.example.org:
  username: <login>
  password: <password>
```

`OswExpress(domain=...)` with no credential arguments reads this file if present;
each connection is matched to the longest IRI it contains.

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

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):
`type(scope): subject`, scope optional. The local `commit-msg` hook (see
Setup) rejects malformed messages, because they drive the automated release
below.

| Type | Release effect |
| ---- | -------------- |
| `feat` | minor release |
| `fix`, `perf` | patch release |
| `BREAKING CHANGE:` footer, or `!` after the type | major release |
| `docs`, `chore`, `test`, `refactor`, `ci`, `style`, `build` | no release |

## Releasing

There is no standing release branch: work goes `feature branch -> main`
directly. Every pull request into `main` runs `main.yml` (quality, tests,
docs), the integration suite, and a `version-preview` job that comments the
version a merge would release, computed with the same conventional commits.

Merging to `main` starts the release job
(`on-release-main.yml`), which pauses on the `pypi` GitHub environment for a
required reviewer to approve -- this is the deliberate-release control, in
place of a staging branch. Once approved,
[python-semantic-release](https://python-semantic-release.readthedocs.io/)
bumps the static version in `pyproject.toml` and `CITATION.cff` (never edited
by hand), updates `CHANGELOG.md`, relocks `uv.lock`, commits, tags `vX.Y.Z`,
builds, publishes to PyPI via trusted publishing and deploys the versioned
docs. Reject the approval and nothing ships.

To preview what the next release would be locally:

```bash
uv run semantic-release --noop version
```
