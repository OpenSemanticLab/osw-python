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

Credentials are prompted for interactively or read from a credentials file;
see [Authentication](api/auth.md).

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
