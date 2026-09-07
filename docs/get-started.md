<!-- markdownlint-disable MD046 -- fenced blocks inside content tabs are indented by design -->

# Get Started

## Prerequisites

- Python **3.10 to 3.13**
- `pip` or [`uv`](https://docs.astral.sh/uv/) (recommended)

## Installation

=== "uv (recommended)"

    ```bash
    uv add osw
    ```

=== "pip"

    ```bash
    pip install osw
    ```

### Optional extras

| Extra | Description |
| ----- | ----------- |
| `osw[wikitext]` | Additional functions in `wiki_tools` to transform mediawiki markup / templates |
| `osw[DB]` | Interact with SQL databases per DatabaseController |
| `osw[S3]` | Interact with S3 stores per S3FileController |
| `osw[dataimport]` | Additional tools to import data |
| `osw[UI]` | To use a helper UI to work with entity slots |
| `osw[all]` | All of the above |

Install multiple extras with `pip install osw[opt1,opt2]`.

## First steps

Create a typed entity locally with the generated data model:

```python
import osw.model.entity as model

my_entity = model.Item(
    label=[model.Label(text="MyItem")],
    statements=[model.DataStatement(property="IsA", value="Category:Item")],
)
print(my_entity.json())
```

Connect to an instance and run a semantic query with
[OswExpress](api/core.md):

```python
from osw.express import OswExpress

osw = OswExpress(domain="wiki-dev.open-semantic-lab.org")
instances = osw.site.semantic_search("[[Category:Item]]")
print(instances)
```

Credentials are resolved from the environment variables `OSW_USERNAME` /
`OSW_PASSWORD` (e.g. loaded from a `.env` file), from an existing
credentials file, or via an interactive prompt - and are held in memory
only, never written to disk; see [Authentication](api/auth.md).

## Logging

osw reports what it is doing through the standard `logging` module, on the
`osw` logger, at INFO by default:

```python
import osw

osw.set_log_level("WARNING")  # see less
osw.set_log_level("DEBUG")    # see more
osw.disable_logging()         # detach the handler osw attached
```

Set `OSW_LOG_LEVEL` to a level name, a level number, or `OFF` to choose the
level before the package is imported. `OFF` silences osw everywhere, including
in your own handlers.

### Collecting osw's records in your application

Configure logging the way you normally would and osw's records arrive there,
once:

```python
import logging
import osw

logging.basicConfig(level=logging.INFO, filename="app.log")
```

The `osw` logger propagates at all times, so the records reach your handlers
whatever else happens. osw's own handler notices that something above it is
listening, detaches itself so nothing is written twice, and gives back the
level it had picked, so your level applies from then on. It makes no difference
whether you configure logging before or after importing osw.

A level you asked for is kept across that hand-over, so `set_log_level("DEBUG")`
or `OSW_LOG_LEVEL=DEBUG` is how you pull osw's debug records into an aggregated
setup while the rest of your application stays quieter.

One case osw cannot detect is a handler added to the `osw` logger itself, since
that is indistinguishable from one of its own. Call `disable_logging()` first if
you do that.

## Examples and tutorials

- Runnable scripts in
  [examples/](https://github.com/OpenSemanticLab/osw-python/tree/main/examples),
  e.g. entity creation, entity manipulation, querying and file downloads
- The [Basics tutorial notebook](https://github.com/OpenSemanticLab/osw-python/blob/main/docs/tutorials/basics.ipynb)
  describes the OpenSemanticLab data model and how to interact with it

## Troubleshooting

### `Error: datamodel-codegen not found`

Make sure `datamodel-codegen` is installed and included in `PATH`, e.g. on
jupyterlab:

```python
os.environ["PATH"] += os.pathsep + "/home/jovyan/.local/bin"
```
