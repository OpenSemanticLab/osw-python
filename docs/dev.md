# Development

## Setup

1. Install [uv](https://docs.astral.sh/uv/)

2. Install the environment and the pre-commit hooks

    ```bash
    make install
    ```

## Quality checks

Run the code quality tools (lock consistency, pre-commit incl. ruff,
ty type checking, deptry):

```bash
make check
```

## Testing

1. Create a new test (file name `test_*.py`) under `/tests`

2. Run pytest in the project root dir (integration tests are excluded
   by default)

    ```bash
    make test
    ```

3. To run the integration tests with credentials, run

    ```bash
    uv run pytest tests/integration -o addopts="" --wiki_domain "<domain>" --wiki_username "<login>" --wiki_password "<password>"
    ```

## Documentation

Serve the docs locally with live reload:

```bash
make docs
```
