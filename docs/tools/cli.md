# CLI

## Quick start

Both adapters need an instance and credentials. The quickest start is a
gitignored `.env` file in your project root:

```dotenv
OSW_DOMAIN=wiki-dev.open-semantic-lab.org
OSW_USERNAME=your-user
OSW_PASSWORD=your-password
```

The CLI searches upward from the working directory for it, so `osw status`
now reports the instance, the username (whether it comes from `OSW_USERNAME`
or a credential file), and connection state. The MCP server takes its
settings from the `env` block of its registration instead, see
[Registering a server](mcp.md#registering-a-server). Every variable is listed
under [Configuration](configuration.md).

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
| `search` | `ask`, `titles`, `content`, `entities`, `sparql` |
| `slot` | `list`, `get`, `set` |
| `schema` | `get` |
| `instances` | `list`, `status` |
| `ledger` | `path` |
| top level | `status` |

`osw search entities` finds pages in the wiki that are instances of a
category, while `osw instances` is about the OSL servers this process can
connect to.

`osw instances list` lists the iris the process can connect to: the
env-configured domain plus every entry of a configured credential file.

`osw instances status` reports the same instances in more detail. For each
one it prints the iri, whether it is the active one, the username that would
be used, and whether a connection succeeded. It never prints passwords. The
instances are contacted one after another and a single attempt has no
timeout, so an unreachable instance delays the command until its connection
attempt gives up.

Global options apply to every command. They belong to the `osw` command
itself, so they come before the subcommand, the same way `git` and `docker`
options do: `osw --instance <iri> status`, not `osw status --instance <iri>`.
Typing them after the subcommand now produces an error that names the correct
form.

- `--instance IRI` picks the instance. Optional: it is only required when
  `OSW_DOMAIN` is not set and the configured credential file holds more than
  one iri.
- `--json` / `-j` writes machine-readable JSON to stdout and keeps osw's own
  progress output on stderr, so it pipes cleanly into `jq`.
- `--read-only` refuses write operations.
- `--verbose` / `-v` shows full tracebacks instead of a one-line message, and
  adds the env-file line to the source report described under
  [Where settings come from](configuration.md#where-settings-come-from).

Failures exit non-zero with a short message on stderr and no traceback.
