# Configuration

Both adapters share the settings below.

## Where settings come from

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

The second line is labelled `env file`. Which lines appear depends on the
adapter:

- **CLI**: the first line only. `--verbose`, or a command that fails, adds
  the second.
- **MCP server**: neither, since its sources are fixed in the server entry.
  `OSW_VERBOSE=true` prints both, and a failed start prints both regardless.

A verbose run of the CLI prints:

```text
[osw] credential file: /home/me/project/accounts.pwd.yaml (accounts.pwd.yaml found in the working directory)
[osw] env file       : /home/me/project/.env (found from the working directory upward)
```

The prefix names the adapter that printed the line: `[osw]` for the CLI,
`[osw-mcp]` for the MCP server. This holds for every message the two share,
not only these two lines.

## Where messages go

The source report above is printed directly, because the adapter's own verbose
flag decides whether it appears, not the log level.

Every other message the adapters produce goes to the `osw` logger, together
with the records of the library itself. A failed connection check and an
unreadable provenance ledger are reported that way. `OSW_LOG_LEVEL` sets how
much of it appears, and an application that configures logging itself takes the
records over. See [Logging](../get-started.md#logging).

Both kinds of message are written to stderr, never to stdout. The MCP server
speaks JSON-RPC over stdout, and the CLI writes its `--json` output there, so
stdout has to stay free.

## Credentials

Keep credentials in a gitignored file. They are read once per process, into that
process only, and never written back to disk. Set either `OSW_USERNAME` and
`OSW_PASSWORD`, or `OSW_CRED_FILEPATH`.

A credential file uses the YAML format osw's `CredentialManager` reads, keyed
by iri (default file name: `accounts.pwd.yaml`):

```yaml
wiki-dev.open-semantic-lab.org:
  username: your-user
  password: your-password
```

A credential file may hold several iris. The CLI selects one automatically if it
is the only one, and otherwise requires `osw --instance <iri>`. The MCP server
never selects one, see [One server per instance](mcp.md).

## Variable reference

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
| `OSW_VERBOSE` | `OSW_MCP_VERBOSE` | `true` prints the configuration source report |

## Windows paths in a `.env` file

Quote them with single quotes, or leave them unquoted. A double-quoted value is
escape-decoded, so `\a` in a path silently becomes a BEL byte that renders as
nothing:

```dotenv
OSW_CRED_FILEPATH='C:\Users\me\accounts.pwd.yaml'   # ok
OSW_CRED_FILEPATH=C:\Users\me\accounts.pwd.yaml     # ok
OSW_CRED_FILEPATH="C:\Users\me\accounts.pwd.yaml"   # broken: \a is eaten
```
