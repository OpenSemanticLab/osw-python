# CLI and MCP tools

Besides the Python API, osw ships two adapters that talk to a live instance:
the `osw` command line client, and an MCP server for agent clients such as
Claude Code. Both run the same operations from one shared, SDK-free core
(`osw.service`), so a command and its matching tool behave identically. They
differ in exactly one way: only the CLI accepts filesystem paths.

## Command line

Installing `osw` also installs an `osw` command:

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
| `search` | `ask`, `text`, `instances`, `sparql` |
| `slot` | `list`, `get`, `set` |
| `schema` | `get` |
| `instance` | `list` |
| `ledger` | `path` |
| top level | `status` |

Global options apply to every command:

- `--instance IRI` selects the instance for this invocation when more than one
  is configured. The CLI is stateless, so the choice is never persisted.
- `--json` / `-j` writes machine-readable JSON to stdout and keeps osw's own
  progress output on stderr, so it pipes cleanly into `jq`.
- `--read-only` refuses write operations.
- `--verbose` / `-v` shows full tracebacks instead of a one-line message.

Failures exit non-zero with a short message on stderr and no traceback.

## Configuration

Both the CLI and the MCP server read their settings from the environment or
from a `.env` file. Keep credentials in a gitignored file; they are read once
per process, into that process only, and never written back to disk. A real
environment variable always wins over the same name in a `.env` file.

```dotenv
OSW_DOMAIN=wiki-dev.open-semantic-lab.org
OSW_USERNAME=your-user
OSW_PASSWORD=your-password
# optional
OSW_SPARQL_ENDPOINT=https://.../sparql
OSW_READ_ONLY=false          # true hides all mutating tools
```

Alternatively, authenticate from an osw credential file, so the password is not
duplicated into a second plaintext file:

```dotenv
OSW_DOMAIN=wiki-dev.open-semantic-lab.org
OSW_CRED_FILEPATH=/abs/path/to/accounts.pwd.yaml
```

The file is the YAML format osw's `CredentialManager` already reads, keyed by
iri, so deployments that configure it need no extra setup:

```yaml
wiki-dev.open-semantic-lab.org:
  username: your-user
  password: your-password
```

A credential file may hold several iris. One is selected automatically only if
it is the only one; otherwise pick it with `osw --instance <iri>`, or pin the
server process with `OSW_DOMAIN`.

The canonical variable names are `OSW_*`. Older `OSW_MCP_*` and `OSL_*` names
stay accepted so existing deployments keep working, and the first name that is
set wins:

| Canonical | Also accepted | Meaning |
| --- | --- | --- |
| `OSW_DOMAIN` | `OSL_DOMAIN` | Instance to connect to |
| `OSW_USERNAME` | `OSL_USERNAME` | Login user |
| `OSW_PASSWORD` | `OSL_PASSWORD` | Login password |
| `OSW_CRED_FILEPATH` | `OSW_MCP_CRED_FILEPATH`, `OSL_CRED_FILEPATH` | YAML credential file, keyed by iri |
| `OSW_ENV_FILE` | `OSW_MCP_ENV_FILE` | `.env` file to load |
| `OSW_READ_ONLY` | `OSW_MCP_READ_ONLY` | `true` refuses every write |
| `OSW_SPARQL_ENDPOINT` | | Endpoint for `sparql` queries |
| `OSW_STATE_DIR` | `OSW_MCP_STATE_DIR` | Where the provenance ledger is kept |
| `OSW_MAX_RESULTS` | `OSW_MCP_MAX_RESULTS` | Default result cap (100) |
| `OSW_MAX_CHARS` | `OSW_MCP_MAX_CHARS` | Result size cap in characters (100000) |

### Where the `.env` file comes from

Set `OSW_ENV_FILE` to a path and that file is loaded, always. With it unset the
two adapters differ on purpose:

- The **CLI** searches upward from the working directory, so a `.env` in a
  project root applies to every `osw` command run anywhere inside it.
- The **MCP server** searches nowhere. Its working directory is picked by the
  MCP client, so an implicit search would make the credentials it loads depend
  on how the client happened to be launched. Point it at a file explicitly with
  `OSW_ENV_FILE` in the server's `env` block (see below).

Both print the sources they resolved to stderr before connecting:

```text
[osw] env file       : /home/me/project/.env (found from the working directory upward)
[osw] credential file: /abs/path/to/accounts.pwd.yaml
```

Quote Windows paths with single quotes, or leave them unquoted. A double-quoted
value in a `.env` file is escape-decoded, so `\a` in a path silently becomes a
BEL byte that renders as nothing:

```dotenv
OSW_CRED_FILEPATH='C:\Users\me\accounts.pwd.yaml'   # ok
OSW_CRED_FILEPATH=C:\Users\me\accounts.pwd.yaml     # ok
OSW_CRED_FILEPATH="C:\Users\me\accounts.pwd.yaml"   # broken: \a is eaten
```

## MCP server

`osw[mcp]` ships an [MCP](https://modelcontextprotocol.io) server that exposes a
live OpenSemanticLab instance to MCP clients such as Claude Code. It wraps
`OswExpress` and provides tools to search (semantic / SPARQL / full-text),
introspect category schemas, read entities and every page slot, create/update
and delete entities, and read and write file pages as text.

```bash
pip install "osw[mcp]"
```

This extra is deliberately not part of `osw[all]`. It needs `anyio>=4.9`, which
conflicts with the pin the `osw[workflow]` extra requires for prefect 2.x, so
the two cannot share an environment
([#139](https://github.com/OpenSemanticLab/osw-python/issues/139)). Installing
the server standalone, for example via `uvx`, avoids the question entirely.

**No filesystem access:** no MCP tool takes or returns a local path. File
content moves inline as text (`get_file_info`, `read_file_text`,
`write_file_text`), and everything path-based lives in the CLI instead
(`osw file download`, `osw file upload`, `osw ledger path`). MCP does not imply
a shared host: a server can be containerised or remote, so a path argument is
either meaningless or a way to reach a filesystem nobody granted access to. A
CLI runs where the command was typed, under that user's own permissions, and an
agent calling it goes through whatever command permissions already apply to it.

**One server per instance:** each server process is pinned to exactly one OSL
instance for its whole lifetime; there is no tool to switch at runtime. If no
instance resolves at startup (a configured `OSW_DOMAIN`, or a credential file
holding exactly one iri), the server refuses to start rather than register
tools that would all fail.

Every setting from the table above can be set in the server entry's `env`
block, so no `.env` file is needed. Pointing at a credential file is the
recommended form: the client config then holds a path and an instance name, and
no secret at all. Never put `OSW_PASSWORD` inline in a committed `.mcp.json`.
The transport is stdio; SSE and HTTP are not supported.

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

`OSW_DOMAIN` may be omitted when the credential file holds exactly one iri.
Setting it anyway is worth the line: the server then checks at startup that the
file has a matching entry and, if not, names the iris the file does contain
(never their secrets) instead of failing later on the first call.

To point at a `.env` file instead, replace the `env` block with
`{ "OSW_ENV_FILE": "/abs/path/to/.env" }`.

Registering the same thing from a shell is easiest with `add-json`, which takes
the entry verbatim. Note that a Windows path needs forward slashes or doubled
backslashes to be valid JSON:

```bash
claude mcp add-json osw '{"type":"stdio","command":"uvx","args":["--from","osw[mcp]","osw-mcp"],"env":{"OSW_CRED_FILEPATH":"/abs/path/to/accounts.pwd.yaml","OSW_DOMAIN":"wiki-dev.open-semantic-lab.org"}}'
```

To work with more than one instance, register one server per instance, each
pinned to a single `OSW_DOMAIN`. One credential file can serve them all, since
it is keyed by iri:

```json
{
  "mcpServers": {
    "osw-dev": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "osw[mcp]", "osw-mcp"],
      "env": {
        "OSW_CRED_FILEPATH": "/abs/path/to/accounts.pwd.yaml",
        "OSW_DOMAIN": "wiki-dev.open-semantic-lab.org"
      }
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

That puts the instance in the tool name at every call site
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

`status` reports the active instance and connection state (never the password).

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
