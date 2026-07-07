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

## Releasing

Maintainers release by pushing a version tag; CI does the rest (build,
publish to PyPI via trusted publishing, deploy versioned docs):

```bash
git tag v1.2.0 && git push origin v1.2.0
```

## AI Guidelines

AI tools may be used to assist development, but a human developer is always
the author: carefully review all generated content for correctness, quality
and license compliance before submitting it.
