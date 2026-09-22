# MCP server

`osw[mcp]` ships an [MCP](https://modelcontextprotocol.io) server that exposes a
live OpenSemanticLab instance to MCP clients such as Claude Code. It wraps
`OswExpress` and provides tools to search (semantic / SPARQL / page titles /
page content),
introspect category schemas, read entities and every page slot, create/update
and delete entities, and read and write file pages as text. The transport is
stdio; SSE and HTTP are not supported.

**No filesystem access:** no MCP tool takes or returns a local path. File
content moves inline as text (`get_file_info`, `read_file_text`,
`write_file_text`), and everything path-based lives in the CLI instead
(`osw file download`, `osw file upload`, `osw ledger path`).

**One server per instance:** each server process is pinned to exactly one OSL
instance for its whole lifetime; there is no tool to switch at runtime.
`OSW_DOMAIN` must be set, either in the server entry's `env` block or in the
`.env` file that entry names. Without it the server refuses to start rather than
register tools that would all fail.

## Quick install

For Claude Code, one command registers the server. Replace the domain and the
credential file path with your own:

```bash
claude mcp add osw-dev \
  -e OSW_DOMAIN=wiki-dev.open-semantic-lab.org \
  -e OSW_CRED_FILEPATH=/abs/path/to/accounts.pwd.yaml \
  -- uvx --from "osw[mcp]" osw-mcp
```

Notes:

- `osw-dev` is the server name and becomes the tool prefix, so every call site
  reads `mcp__osw-dev__get_entity`. Pick one name per instance, e.g. `osw-prod`.
- `osw-mcp` is the program `uvx` runs. It is the console script this package
  installs, so it does not change.
- On Windows, write the path with forward slashes.
- The default scope is `local`: this project, your machine only. Use `-s user`
  for every project, or `-s project` to write a shared `.mcp.json`.
- List what is registered with `claude mcp list`.

### `uvx` or the installed command

The other examples on this page run the server with `uvx`, which needs no
install of its own. If you installed `osw[mcp]` with `uv tool install`
([Setup](index.md#setup)), register the `osw-mcp` command directly instead and
drop the `--from` argument:

```bash
claude mcp add osw-dev \
  -e OSW_DOMAIN=wiki-dev.open-semantic-lab.org \
  -e OSW_CRED_FILEPATH=/abs/path/to/accounts.pwd.yaml \
  -- osw-mcp
```

In JSON, that entry is `"command": "osw-mcp"` with an empty `args` array. Every
other part of an entry, `env` included, stays the same.

Which one to pick depends on how many instances you register. With `uvx`, the
package specification is part of every entry, so pinning a version or pointing
at a checkout means editing every entry in every client. With the installed
command, an entry names only `osw-mcp`, and `uv tool install` or
`uv tool upgrade osw` decides what that runs. The trade-off is that `osw-mcp`
has to be on the PATH of the client, and that all registered servers change
version together.

## Registering a server

A server entry can carry its settings in two ways:

- **Directly in the entry's `env` block.** Every variable from the
  [reference table](configuration.md#variable-reference) can be set there, so
  no `.env` file is needed at all.
- **In a `.env` file**, named by `OSW_ENV_FILE` in the `env` block. Useful when
  several tools share one settings file, or when the client config is committed
  and the settings file is not.

Prefer the `env` block naming `OSW_CRED_FILEPATH` and `OSW_DOMAIN`, so the
destination instance is visible in the entry itself. Never put `OSW_PASSWORD`
in a committed `.mcp.json`.

```json
{
  "mcpServers": {
    "osw": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "osw[mcp]", "osw-mcp"],
      "env": {
        "OSW_CRED_FILEPATH": "/abs/path/to/accounts.pwd.yaml",
        "OSW_DOMAIN": "wiki-dev.open-semantic-lab.org"
      }
    }
  }
}
```

At startup the server checks that the credential file has an entry matching
`OSW_DOMAIN`. If it does not, the server stops and names the iris the file does
contain, never their secrets.

Registering the same entry from a shell is easiest with `add-json`, which takes
it verbatim. Note that a Windows path needs forward slashes or doubled
backslashes to be valid JSON:

```bash
claude mcp add-json osw '{"type":"stdio","command":"uvx","args":["--from","osw[mcp]","osw-mcp"],"env":{"OSW_CRED_FILEPATH":"/abs/path/to/accounts.pwd.yaml","OSW_DOMAIN":"wiki-dev.open-semantic-lab.org"}}'
```

## More than one instance

Register one server per instance, each pinned to a single `OSW_DOMAIN`. The two
entries below show both styles side by side: `osw-dev` puts everything in a
`.env` file, `osw-prod` names the credential file and the domain directly. One
credential file can serve any number of servers, since it is keyed by iri.

```json
{
  "mcpServers": {
    "osw-dev": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "osw[mcp]", "osw-mcp"],
      "env": { "OSW_ENV_FILE": "/abs/path/to/dev.env" }
    },
    "osw-prod": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "osw[mcp]", "osw-mcp"],
      "env": {
        "OSW_CRED_FILEPATH": "/abs/path/to/accounts.pwd.yaml",
        "OSW_DOMAIN": "wiki.open-semantic-lab.org",
        "OSW_READ_ONLY": "true"
      }
    }
  }
}
```

`dev.env` has to pin the instance itself, since the server will not infer one:

```dotenv
OSW_DOMAIN=wiki-dev.open-semantic-lab.org
OSW_CRED_FILEPATH=/abs/path/to/accounts.pwd.yaml
```

The instance is then part of the tool name at every call site
(`mcp__osw-prod__get_entity`), so the destination is visible in the permission
prompt, read-only is settable per instance, and permissions can differ per
instance:

```json
{
  "permissions": {
    "allow": ["mcp__osw-dev"],
    "ask": ["mcp__osw-prod"]
  }
}
```

## Notes and caveats

- `status` reports the active instance and connection state, never the password.
- **Safe deletes:** the server records every entity it creates or modifies in a
  local provenance ledger. It deletes those without extra prompting, but refuses
  to delete anything it did not create unless the caller passes
  `confirm_external_delete=true`.

## Design notes

Why the MCP server is shaped the way it is, and how that differs from the CLI:

- **No filesystem access on the MCP surface.** MCP does not imply a shared host:
  a server can be containerised or remote, so a path argument is either
  meaningless or a way to reach a filesystem nobody granted access to. A CLI
  runs where the command was typed, under that user's own permissions, and an
  agent calling it goes through whatever command permissions already apply.
- **One instance per server process.** Which instance a tool call reaches has to
  be readable from the configuration rather than inferred, so the server never
  picks one for you, not even when the credential file holds exactly one iri.
- **stdio only.** SSE is deprecated upstream, and HTTP would need a
  per-connection auth model this server does not have: it holds one set of wiki
  credentials, which every client would share.
- **`mcp` is an extra, not a base dependency.** The SDK pulls in a server stack
  (starlette, uvicorn, sse-starlette) that nothing in the Python API or the CLI
  needs, so only users who actually run the server pay for it.

## Notes for developers

To try an unreleased branch against a real client, point `uvx` at the checkout
instead of at PyPI. Everything else about the registration stays the same:

```bash
uvx --reinstall --from "/abs/path/to/osw-python[mcp]" osw-mcp
```

`--reinstall` is what picks up your latest edits, since `uvx` caches the wheel
it builds. In a JSON `args` array, a Windows path needs forward slashes or
doubled backslashes.

The alternative is an editable tool install
([From a local checkout](index.md#from-a-local-checkout)). The server then
registers as plain `osw-mcp`, no client config contains the checkout path, and
edits take effect at the next server start without a `--reinstall`.

One difference decides between the two. `create_or_update_entity` and
`export_entity_jsonld` call `fetch_schema`, which regenerates
`src/osw/model/entity.py` inside the installed package. `uvx` builds a
non-editable wheel, so the regenerated file is written into the uv cache. Under
an editable install, as under `pip install -e` or `uv sync`, it is written into
your working tree, where git tracks it. Note that `export_entity_jsonld` is
declared read-only and still triggers this. The remaining read tools
(`get_entity`, `get_slot`, `get_category_schema`, ...) read raw page slots and
never trigger it. So choose `uvx` whenever a client may call either of those two
operations, and the editable install otherwise.
