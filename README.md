[![PyPI-Server](https://img.shields.io/pypi/v/osw.svg)](https://pypi.org/project/osw/)
[![DOI](https://zenodo.org/badge/458130867.svg)](https://zenodo.org/badge/latestdoi/458130867)
[![Codecov](https://codecov.io/gh/OpenSemanticLab/osw-python/graph/badge.svg)](https://codecov.io/gh/OpenSemanticLab/osw-python)
[![docs](https://img.shields.io/badge/docs-online-blue)](https://opensemanticlab.github.io/osw-python/)
![license](https://img.shields.io/github/license/OpenSemanticLab/osw-python.svg)

# osw

Python toolset for data processing, queries, wikicode generation and page
manipulation within [OpenSemanticLab](https://github.com/OpenSemanticLab).

Work with OpenSemanticLab instances the way you work with Python objects:
load pages as typed pydantic entities, query with semantic search, generate
models from the schemas stored in the wiki, and write changes back.

**Documentation: <https://opensemanticlab.github.io/osw-python/>**

## Installation

```bash
pip install osw
```

Optional extras (`osw[wikitext]`, `osw[DB]`, `osw[S3]`, `osw[dataimport]`,
`osw[UI]`, `osw[mcp]`, `osw[all]`) are described in the
[Get Started guide](https://opensemanticlab.github.io/osw-python/get-started/).

## Quickstart

```python
from osw.express import OswExpress

osw = OswExpress(domain="wiki-dev.open-semantic-lab.org")
instances = osw.site.semantic_search("[[Category:Item]]")
print(instances)
```

More runnable scripts live in [examples/](examples/), and the
[Basics tutorial](docs/tutorials/basics.ipynb) walks through the
OpenSemanticLab data model.

## MCP server

`osw[mcp]` ships an [MCP](https://modelcontextprotocol.io) server that exposes a
live OpenSemanticLab instance to MCP clients such as Claude Code. It wraps
`OswExpress` and provides tools to search (semantic / SPARQL / full-text),
introspect category schemas, read entities and every page slot, create/update
and delete entities, and upload/download files.

```bash
pip install "osw[mcp]"
```

Configure credentials in a gitignored `.env` file (the server reads them at
startup and never writes them to disk):

```dotenv
OSW_DOMAIN=wiki-dev.open-semantic-lab.org
OSW_USERNAME=your-user
OSW_PASSWORD=your-password
# optional
OSW_SPARQL_ENDPOINT=https://.../sparql
OSW_MCP_READ_ONLY=false          # true hides all mutating tools
```

Register it with Claude Code (reference the `.env` via `OSW_MCP_ENV_FILE`; do
not put `OSW_PASSWORD` inline in a committed `.mcp.json`):

```json
{
  "mcpServers": {
    "osw": {
      "command": "uvx",
      "args": ["--from", "osw[mcp]", "osw-mcp"],
      "env": { "OSW_MCP_ENV_FILE": "/abs/path/to/.env" }
    }
  }
}
```

Or via the CLI:

```bash
claude mcp add osw --env OSW_MCP_ENV_FILE=/abs/path/to/.env -- uvx --from "osw[mcp]" osw-mcp
```

**Safe deletes:** the server records every entity it creates or modifies in a
local provenance ledger. It deletes those without extra prompting, but refuses
to delete anything it did not create unless the caller passes
`confirm_external_delete=true`.

**Editable-checkout caveat:** `create_or_update_entity` and
`export_entity_jsonld` call `fetch_schema`, which regenerates
`src/osw/model/entity.py` inside the installed package. With a normal
`pip install "osw[mcp]"` this writes into site-packages and is harmless. If you
run the server from an editable source checkout, those two tools will modify the
generated model file in your working tree. The read tools (`get_entity`,
`get_slot`, `get_category_schema`, ...) read raw page slots and never trigger
this.

## Contributing

Contributions are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md).
Development setup, checks and tests are one command each: `make install`,
`make check`, `make test`.

## Related projects

General features for object-oriented interaction with knowledge graphs live
in the standalone package [oold-python](https://github.com/OO-LD/oold-python).

## License

AGPL-3.0-or-later, see [LICENSE.txt](LICENSE.txt).
