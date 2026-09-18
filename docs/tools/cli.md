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
| `schema` | `get`, `props` |
| `task` | `create`, `update`, `list`, `list-projects`, `list-persons`, `create-person`, `render` |
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

Failures exit non-zero with a short message on stderr and no traceback.

## Tasks and projects

The `task` group reads local todos into an OSL wiki as Task entities, and
reads tasks, projects and persons back out. It is built on three OSL core
categories (Task, Person, Project); every operation takes plain typed
parameters and returns a small flat dict, never a JSON Schema.

| Command | Tool | Purpose |
| --- | --- | --- |
| `osw task create` | `create_task` | Create a task. |
| `osw task update` | `update_task` | Merge fields into an existing task. |
| `osw task list` | `list_tasks` | List tasks, filtered by project, actionee, status or label text. |
| `osw task list-projects` | `list_projects` | Find a project's page name. |
| `osw task list-persons` | `list_persons` | Find a person's page name. |
| `osw task create-person` | `create_person` | Create a person, as a fallback for when one is genuinely absent. |
| `osw task render` | not available | Render a Markdown table of tasks to a local file. |

`render` is CLI only: it names a local output path, and no MCP tool takes or
returns a path.

**Configuration.** Four environment variables affect these operations, and
all are optional: `OSW_PERSON_IRI`, `OSW_TASK_CATEGORY`, `OSW_PERSON_CATEGORY`
and `OSW_PROJECT_CATEGORY`. Reading always queries the shared OSL core
category, since MediaWiki category membership includes the whole subclass
tree, so a task kept in a local subclass is found without any configuration.
The three category overrides only change where a newly created task, person
or project is written.

**Vocabularies.** `status` is one of `to do`, `in work`, `done`. `prio` is one
of `high`, `medium`, `low`. A due date is written to `end_date_time`, since
the Task category has no due-date property.

### The Claude Code skill

The skill that drives this group ships at `src/osw/skills/osl-tasks/SKILL.md`.
Install it one of two ways:

1. `osw skill install`, which copies it to `~/.claude/skills/osl-tasks/`.
2. `/plugin marketplace add OpenSemanticLab/osw-python` then
   `/plugin install osl-tasks`.

A new Claude Code session picks it up with no further action.
