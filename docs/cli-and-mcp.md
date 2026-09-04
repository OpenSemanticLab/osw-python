# CLI and MCP tools

Besides the Python API, osw ships two adapters that talk to a live instance:
the `osw` command line client, and an MCP server for agent clients such as
Claude Code. Both run the same operations from one shared, SDK-free core
(`osw.service`), so a command and its matching tool behave identically. They
differ in exactly one way: only the CLI accepts filesystem paths.

## Setup

Install one of the two; the second includes the first:

```bash
uv tool install osw             # the `osw` command
uv tool install "osw[mcp]"      # the same, plus the `osw-mcp` server
```

<details markdown="1">
<summary>Other ways to install</summary>

```bash
pip install "osw[mcp]"          # into the active environment
uv add "osw[mcp]"               # as a dependency of the current uv project
uvx --from "osw[mcp]" osw-mcp   # run the server without installing it
```

`uvx` is what the registration examples further down use, so the server needs
no install of its own.

</details>

`osw[mcp]` is also part of `osw[all]`. The other extras are listed in the
[Get Started guide](get-started.md#optional-extras).

Both adapters need an instance and credentials. The quickest start is a
gitignored `.env` file in your project root:

```dotenv
OSW_DOMAIN=wiki-dev.open-semantic-lab.org
OSW_USERNAME=your-user
OSW_PASSWORD=your-password
```

The CLI searches upward from the working directory for it, so `osw status` now
reports the instance and connection state. The MCP server takes its settings
from the `env` block of its registration instead, see
[Registering a server](#registering-a-server). Every variable is listed under
[Configuration](#configuration).

## Command line

```bash
osw status
osw search ask '[[Category:Item]]' --limit 5
osw entity get 'Item:OSW1234...' --json | jq .
osw file cat 'File:Example.csv'                            # inline text
osw file download 'File:Example.csv' --target-dir ./tmp    # to disk
```

Commands are grouped by subject:

| Group | Commands |
| --- | --- |
| `entity` | `get`, `put`, `export`, `delete` |
| `file` | `info`, `cat`, `write`, `download`, `upload` |
| `search` | `ask`, `titles`, `content`, `instances`, `sparql` |
| `slot` | `list`, `get`, `set` |
| `schema` | `get` |
| `instance` | `list` |
| `ledger` | `path` |
| top level | `status` |

Global options apply to every command:

- `--instance IRI` picks the instance. Optional: it is only required when
  `OSW_DOMAIN` is not set and the configured credential file holds more than
  one iri.
- `--json` / `-j` writes machine-readable JSON to stdout and keeps osw's own
  progress output on stderr, so it pipes cleanly into `jq`.
- `--read-only` refuses write operations.
- `--verbose` / `-v` shows full tracebacks instead of a one-line message, and
  adds the env-file line to the source report described under
  [Where settings come from](#where-settings-come-from).

Failures exit non-zero with a short message on stderr and no traceback.

## MCP server

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

### Quick install

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

### Registering a server

A server entry can carry its settings in two ways:

- **Directly in the entry's `env` block.** Every variable from the
  [reference table](#variable-reference) can be set there, so no `.env` file is
  needed at all.
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

### More than one instance

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

### Notes and caveats

- `status` reports the active instance and connection state, never the password.
- **Safe deletes:** the server records every entity it creates or modifies in a
  local provenance ledger. It deletes those without extra prompting, but refuses
  to delete anything it did not create unless the caller passes
  `confirm_external_delete=true`.

## Configuration

Both adapters share the settings below.

### Where settings come from

Settings are read from the process environment. A `.env` file fills that
environment; a real environment variable wins over the same name in a file.

**Env file**

| `OSW_ENV_FILE` | CLI | MCP server |
| --- | --- | --- |
| set | loads that file, searches nowhere | loads that file, searches nowhere |
| unset | searches upward from the working directory | searches nowhere |

**Credential file.** The first step that produces a file wins:

1. `OSW_CRED_FILEPATH` or an alias, set in the environment or the env file.
   The run fails if this file has no entry for `OSW_DOMAIN`. That check is
   skipped when `OSW_USERNAME` and `OSW_PASSWORD` are both set.
2. CLI only: `accounts.pwd.yaml` in the working directory. Parent directories
   are not searched. This step is skipped when `OSW_USERNAME` or
   `OSW_PASSWORD` is set. If the file has no entry for `OSW_DOMAIN` it is
   ignored and the run continues.
3. No credential file.

**Source report.** Both adapters write to stderr before connecting. The first
line is labelled `credential file` when a file was found:

- `<path> (from the OSW_CRED_FILEPATH environment variable)`
- `<path> (from OSW_CRED_FILEPATH in the env file)`
- `<path> (accounts.pwd.yaml found in the working directory)`
- `<path> (accounts.pwd.yaml found in the working directory, ignored: no entry for domain '<domain>')`

and `credentials` when none was:

- `OSW_USERNAME/OSW_PASSWORD (from the environment)`
- `OSW_USERNAME/OSW_PASSWORD (from the env file)`
- `not configured (set OSW_CRED_FILEPATH, or OSW_USERNAME/OSW_PASSWORD)`

The second line is labelled `env file`. The MCP server prints both lines. The
CLI prints the first only, adding the second with `--verbose` or when the
command fails:

```text
[osw] credential file: /home/me/project/accounts.pwd.yaml (accounts.pwd.yaml found in the working directory)
[osw] env file       : /home/me/project/.env (found from the working directory upward)
```

### Credentials

Keep credentials in a gitignored file. They are read once per process, into that
process only, and never written back to disk. Set either `OSW_USERNAME` and
`OSW_PASSWORD`, or `OSW_CRED_FILEPATH`.

A credential file uses the YAML format osw's `CredentialManager` reads, keyed
by iri:

```yaml
wiki-dev.open-semantic-lab.org:
  username: your-user
  password: your-password
```

A credential file may hold several iris. The CLI selects one automatically if it
is the only one, and otherwise requires `osw --instance <iri>`. The MCP server
never selects one, see [One server per instance](#mcp-server).

### Variable reference

The canonical variable names are `OSW_*`. Older `OSW_MCP_*` and `OSL_*` names
stay accepted so existing deployments keep working, and the first name that is
set wins:

| Canonical | Also accepted | Meaning |
| --- | --- | --- |
| `OSW_DOMAIN` | `OSL_DOMAIN` | Instance to connect to |
| `OSW_USERNAME` | `OSL_USERNAME` | Login user |
| `OSW_PASSWORD` | `OSL_PASSWORD` | Login password |
| `OSW_CRED_FILEPATH` | `OSW_MCP_CRED_FILEPATH`, `OSL_CRED_FILEPATH` | YAML credential file, keyed by iri (falls back to `accounts.pwd.yaml` in the working directory, CLI only) |
| `OSW_ENV_FILE` | `OSW_MCP_ENV_FILE` | `.env` file to load |
| `OSW_READ_ONLY` | `OSW_MCP_READ_ONLY` | `true` refuses every write |
| `OSW_SPARQL_ENDPOINT` | | Endpoint for `sparql` queries |
| `OSW_STATE_DIR` | `OSW_MCP_STATE_DIR` | Where the provenance ledger is kept |
| `OSW_MAX_RESULTS` | `OSW_MCP_MAX_RESULTS` | Default result cap (100) |
| `OSW_MAX_CHARS` | `OSW_MCP_MAX_CHARS` | Result size cap in characters (100000) |

### Windows paths in a `.env` file

Quote them with single quotes, or leave them unquoted. A double-quoted value is
escape-decoded, so `\a` in a path silently becomes a BEL byte that renders as
nothing:

```dotenv
OSW_CRED_FILEPATH='C:\Users\me\accounts.pwd.yaml'   # ok
OSW_CRED_FILEPATH=C:\Users\me\accounts.pwd.yaml     # ok
OSW_CRED_FILEPATH="C:\Users\me\accounts.pwd.yaml"   # broken: \a is eaten
```

## Design notes

Why the two adapters are shaped the way they are:

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

Prefer that over an editable install for the server. `create_or_update_entity`
and `export_entity_jsonld` call `fetch_schema`, which regenerates
`src/osw/model/entity.py` inside the installed package: `uvx` builds a
non-editable wheel, so the write lands in the uv cache, while under
`pip install -e` or `uv sync` it lands in your working tree. The read tools
(`get_entity`, `get_slot`, `get_category_schema`, ...) read raw page slots and
never trigger it.
