# Contributing

Contributions are welcome! File issues and pull requests at
[github.com/OpenSemanticLab/osw-python](https://github.com/OpenSemanticLab/osw-python).

## Workflow

Requires [uv](https://docs.astral.sh/uv/) and `git`.

```bash
git clone git@github.com:YOUR_NAME/osw-python.git
cd osw-python
make install    # environment + pre-commit hooks
```

1. Create a branch: `git checkout -b name-of-your-fix`
2. Make your changes and add tests in `tests/`
3. Run `make check` (lint, type-check, dependency audit) and `make test`
4. Commit, push and open a pull request

`make help` lists all targets; the
[development guide](https://opensemanticlab.github.io/osw-python/dev/)
covers details such as running the integration tests and serving the docs
locally.

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):
`type(scope): subject`, for example `fix: correct sidebar collapse on small
screens`. The scope is optional. A local `commit-msg` hook (installed by
`make install`) rejects malformed messages, because they drive the automated
release below.

| Type | Release effect |
| ---- | -------------- |
| `feat` | minor release |
| `fix`, `perf` | patch release |
| `BREAKING CHANGE:` footer, or `!` after the type | major release |
| `docs`, `chore`, `test`, `refactor`, `ci`, `style`, `build` | no release |

## Releasing

There is no standing release branch: work goes `feature branch -> main`.
Every pull request into `main` runs the checks, the integration suite, and a
bot comment predicting the version a merge would release. Merging starts the
release job, which pauses on the `pypi` GitHub environment for a required
reviewer to approve; approve and
[python-semantic-release](https://python-semantic-release.readthedocs.io/)
bumps the version (in `pyproject.toml`, never edited by hand), updates the
changelog, tags, builds, publishes to PyPI via trusted publishing and deploys
the versioned docs. Reject the approval and nothing ships.

## AI Guidelines

AI tools may be used to assist development, but a human developer is always
the author: carefully review all generated content for correctness, quality
and license compliance before submitting it.
