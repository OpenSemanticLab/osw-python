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

## Citation and Authorship

Authors of the project are listed explicitly in
[`CITATION.cff`](CITATION.cff). This list is the set of creators shown on
each [Zenodo](https://zenodo.org/doi/10.5281/zenodo.7799493) release. We keep
it opt-in and curated rather than auto-generated from GitHub, so nobody is
listed without consent, and the entries in `CITATION.cff` take precedence
over GitHub's automatic contributor detection.

To be officially listed as an author for future Zenodo releases, add
yourself to the `authors:` list in `CITATION.cff`. Two ways, in order of
preference:

1. **Preferred, within your feature PR:** include the `CITATION.cff` edit
   directly in the same PR that contributes your feature or fix, so
   authorship is recorded together with the work.
2. **Standalone PR:** if you are already a GitHub contributor and simply
   want to be listed as an author on Zenodo, open a single PR that only adds
   your entry.

In either case, add an entry like:

```yaml
  - given-names: Your
    family-names: Name
    affiliation: "Your institution"                 # optional
    orcid: "https://orcid.org/0000-0000-0000-0000"  # optional, use your real ORCID
```

Notes:

- Append yourself to the end of the list (order is the citation order);
  mention it in the PR if a different position is intended.
- `affiliation` and `orcid` are optional but recommended for durable,
  unambiguous attribution.
- Only entries present in `CITATION.cff` at the tagged commit appear on that
  release's Zenodo record, so add yourself before a release to be included.

## AI Guidelines

AI tools may be used to assist development, but a human developer is always
the author: carefully review all generated content for correctness, quality
and license compliance before submitting it.
