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
| `entity` | `get`, `put`, `export`, `delete`, `validate` |
| `file` | `info`, `cat`, `write`, `download`, `upload` |
| `search` | `ask`, `titles`, `content`, `entities`, `sparql`, `label` |
| `slot` | `list`, `get`, `set` |
| `schema` | `get`, `props`, `usage` |
| `skill` | `install` |
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
- `--version` / `-V` prints one line with the osw version, the location of
  the osw package and the Python version, then exits, needing no instance or
  credentials.

`--help` / `-h` works on `osw` itself and after any subcommand or group, e.g.
`osw entity --help` or `osw entity get -h`, and prints that command's own
help.

Failures exit non-zero with a short message on stderr and no traceback.

## Tasks and projects

There is no dedicated command group for tasks. Reading local todos into an
OSL wiki as Task entities, and reading tasks, projects and persons back out,
is done with the generic `entity`, `schema` and `search` commands against the
three OSL core categories (Task, Person, Project).

**Configuration.** Four environment variables affect this, and all are
optional: `OSW_PERSON_IRI`, `OSW_TASK_CATEGORY`, `OSW_PERSON_CATEGORY` and
`OSW_PROJECT_CATEGORY`. Reading always queries the shared OSL core category,
since MediaWiki category membership includes the whole subclass tree, so a
task kept in a local subclass is found without any configuration. The three
category overrides only change where a newly created task, person or project
is written.

**Vocabularies.** `status` and `prio` store the page name of a wiki item, not
a word. Read the allowed values from the category schema with `osw schema get
<task category> --resolve`: `status` carries them in `enum`, and `prio` names
the category that holds them in `range`. A stock instance offers To do, In
work and Done for `status`, and High, Medium and Low for `prio`. A due date is
written to `end_date_time`, since the Task category has no due-date property.

### The Claude Code skill

The skill that drives this ships at `src/osw/skills/osl-tasks/SKILL.md`.
Install it one of two ways:

1. `osw skill install`, which copies it to `~/.claude/skills/osl-tasks/`.
2. `/plugin marketplace add OpenSemanticLab/osw-python` then
   `/plugin install osl-tasks`.

A new Claude Code session picks it up with no further action.

Path 2 installs the skill file only. The skill drives the `osw` CLI and the
MCP server, so install the package separately, and register the MCP server as
described in [MCP server](mcp.md).
