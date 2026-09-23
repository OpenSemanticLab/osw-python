---
name: osl-tasks
description: Use when importing local todo or note files into an OpenSemanticLab (OSL) wiki as Task entities, or when listing, filtering and updating tasks that already live in OSL. Requires the `osw` CLI or the osw MCP server.
metadata:
  version: "2.8.1"
---

# OSL task management

Read todos from local files, create them as Task entities in an OSL wiki, and
read tasks back.

There is no task-specific operation. Everything here uses the generic
operations that work on any OSL category. What is specific to tasks is written
in this file: which categories to use, which field holds what, and which
mistakes silently produce a wrong result.

Commands are shown in CLI form. Each one has an MCP tool with the same
parameters; the tool name is given in the table below.

## What this skill needs

This skill calls the `osw` CLI or the osw MCP server, and installing the skill
file or the `osl-tasks` plugin installs neither of them. Run `osw schema
--help` first. It fails when the CLI is missing, and when it is old enough to
lack the command groups below. It does not tell you whether the version
matches this file. Troubleshooting covers that. If it fails and this session
has no osw MCP tool, ask the
user to install the `osw` package, plus the `mcp` extra and a registered
server for the MCP tools. Then stop.

## When to use this skill

- Importing todos or notes from a local file into OSL.
- Listing or filtering the tasks of a project or a person.
- Updating the status, priority, actionees or due date of a task.
- Writing a local Markdown view of the tasks.

## The operations this skill uses

| CLI | MCP tool | Used for |
| --- | --- | --- |
| `osw schema get <category> --resolve` | `get_category_schema` | Field names, and the status and priority vocabularies. |
| `osw schema props <category>` | `get_category_property_map` | The SMW property name of each field, for queries. |
| `osw search ask '<query>'` | `search_ask` | Listing and filtering tasks. |
| `osw search label '<label>' --category <c>` | `search_by_label` | Resolving a person or a project by name. |
| `osw entity get <title>` | `get_entity` | Reading a task before updating it. |
| `osw entity put <category> --jsondata '<json>'` | `create_or_update_entity` | Creating and updating. |
| `osw entity validate <category> --jsondata '<json>'` | `validate_entity` | Checking a payload without writing it. |

Add `--json` before the group name for machine-readable CLI output, for
example `osw --json search ask '[[Category:Item]]'`.

## The category page names

These three names are the only values this skill cannot discover at runtime.
They come from the shared OSL core data model and are the same on every
instance that imports it.

| Kind | Category page name |
| --- | --- |
| Task | `Category:OSWc5d4829ed2744a219ba027171c75fa1d` |
| Person | `Category:OSW44deaa5b806d41a2a88594f562b110e9` |
| Project | `Category:OSWb2d7e6a2eff94c82b7f1f2699d5b0ee3` |

An instance may define its own subclass, for example a local "ISC User"
subclass of Person. Query the core category anyway. `search label` and a
`[[Category:...]]` clause in `search ask` both match the whole subclass tree,
so instances of a local subclass are found without any configuration. Use the
subclass name only when writing a new entity that has to land in it.

## The environment variables

No command reads these four. Read them yourself, from the shell or from the
`.env` file the instance uses. All four are optional.

Through the MCP server you cannot read them at all. The server is a separate
process with its own environment and its own env file, and no tool reports
either. Ask the user for the value in that case.

| Variable | Meaning |
| --- | --- |
| `OSW_PERSON_IRI` | The page name of the operator's own Person entity. Needed to answer "my tasks". |
| `OSW_TASK_CATEGORY` | Write a new task to this category instead of the core one. |
| `OSW_PERSON_CATEGORY` | Write a new person to this category instead of the core one. |
| `OSW_PROJECT_CATEGORY` | Write a new project to this category instead of the core one. |

The three category variables affect writing only. Always read and search
through the core category from the table above, because it covers the
subclasses as well.

## Read the schema once per session

Run this before the first write:

```
osw --json schema get Category:OSWc5d4829ed2744a219ba027171c75fa1d --resolve
```

It gives the field names and both vocabularies. In `properties`:

- `status.enum` holds the page names of the allowed status items, and
  `status.options.enum_titles` holds their human labels in the same order.
  The labels are under `options`, not beside `enum`. A stock instance returns
  three: "To do", "In work", "Done".
- `prio` has no `enum`. It carries `range`, the page name of the priority
  category. List its items with
  `osw --json search entities <that category>` and read each label, or use
  `osw --json search ask '[[<that category>]]' --printouts HasLabel`. A stock
  instance returns three: High, Medium, Low.
- `actionees.items.range` is the Person category and confirms the name above.

Never write a status or priority string. The field stores a page name
(`Item:OSW...`), taken from the schema.

There is no alias table. Map the user's wording onto the labels you read
yourself: "wip", "in progress" and "doing" all mean "In work"; "todo", "open"
and "backlog" mean "To do"; "closed", "complete" and "finished" mean "Done".
When the wording fits no label, ask the user rather than guessing, and say
which labels the instance offers.

## The field map

The Task category does not name its fields the way a todo list does.

| What you mean | Field in `jsondata` | Shape |
| --- | --- | --- |
| Title of the todo | `label` | `[{"text": "...", "lang": "en"}]` |
| Longer text | `description` | `[{"text": "...", "lang": "en"}]` |
| Status | `status` | `"Item:OSW..."` from the schema enum |
| Priority | `prio` | `"Item:OSW..."` from the priority category |
| Project | `related_to` | `["Item:OSW..."]` |
| Assigned people | `actionees` | `["Item:OSW...", ...]` |
| Due date | `end_date_time` | `"2026-12-31T00:00:00Z"` |

Two of these are not deducible from the schema:

- **A project goes into `related_to`.** The schema declares its range as the
  top type `Category:Entity`, so the schema does not say that a project
  belongs there. `related_to` is also the field the OSL task views read.
- **There is no due-date field.** The due date is the task's end time, so it
  goes into `end_date_time`. A date without a time means midnight UTC.

## Creating a task

```
osw entity put Category:OSWc5d4829ed2744a219ba027171c75fa1d --jsondata '{
  "type": ["Category:OSWc5d4829ed2744a219ba027171c75fa1d"],
  "label": [{"text": "Fix the parser", "lang": "en"}],
  "status": "Item:OSW...",
  "prio": "Item:OSW...",
  "related_to": ["Item:OSW..."],
  "actionees": ["Item:OSW..."],
  "end_date_time": "2026-12-31T00:00:00Z"
}' --comment "Imported from todo.md"
```

Leave out any field you have no value for. A task with no `status` is valid,
but the OSL task views filter by status, so set it. Use the item for "To do"
unless the todo says otherwise.

**Validate the first task of a run before you write it.** Replace `put` with
`validate` and send the same `jsondata`:

```
osw --json entity validate Category:OSWc5d4829ed2744a219ba027171c75fa1d --jsondata '<the same object>'
```

It writes nothing and checks the values against the category schema, so a
status page name you got wrong is reported as
`$.status: 'Item:OSW...' is not one of [...]` instead of being stored. Do this
once per run, not once per task; a later task in the same run reuses fields
that are already proven correct.

The result reports `created`, `updated` and `skipped`, plus `titles` and
`urls`. A create must show the page under `created`. If it shows up under
`updated`, the page already existed and you have overwritten it.

## Updating a task

Read the entity, change the one field, and write the whole `jsondata` back.

```
osw --json entity get Item:OSW1234...
# take the "jsondata" object from the result, set "status", write it back
osw entity put Category:OSWc5d4829ed2744a219ba027171c75fa1d --jsondata '<the whole object>'
```

Two rules make the read step necessary.

- **The `jsondata` you send has to carry the stored `uuid`.** The page name is
  derived from the uuid. Without one, a fresh uuid is generated and the write
  lands on a new page. That creates a duplicate and reports no error.
- **It also has to carry every required field, `label` among them.** Sending
  only `uuid` and the changed field fails with `ValidationError: label field
  required`. The entity is validated as a whole model before the merge runs,
  so a partial object is rejected even though the merge would have kept the
  stored label.

The default `--overwrite true` then merges field by field into the stored
entity, so sending the full object changes nothing you did not edit. Confirm
the result lists the page under `updated`, not `created`.

Two other values of `--overwrite` are traps:

- `keep existing` writes nothing at all to a page that already exists. The
  result reports it under `skipped`. Do not use it for an update.
- `replace remote` erases every field you did not supply.

**A list field replaces the stored list, it does not extend it.** To add one
actionee, read the stored `actionees` with `entity get`, append to that list,
and write the whole list back.

**An empty value cannot clear a field.** `null`, `""`, `[]` and `{}` are
stripped out of your `jsondata` before the merge runs, so the stored value
survives. To clear a field, send the full object without that field and add
`--overwrite "replace remote"`, or edit the slot directly with
`osw slot set <title> jsondata '<json>'`.

## Listing and filtering tasks

Ask queries use SMW property names, not JSON field names. Read them with:

```
osw --json schema props Category:OSWc5d4829ed2744a219ba027171c75fa1d
```

A stock instance maps `status` to `HasStatus`, `prio` to `HasPriority`,
`related_to` to `IsRelatedTo`, `actionees` to `HasActionee`, `label` to
`HasLabel` and `end_date_time` to `HasEndDateAndTime`. Read the map rather
than trusting that list; an instance can declare its own.

```
# every task of one project, with status and priority in the same result
osw --json search ask \
  '[[Category:OSWc5d4829ed2744a219ba027171c75fa1d]][[IsRelatedTo::Item:OSW3660...]]' \
  --printouts HasStatus --printouts HasPriority --printouts HasActionee

# the open tasks of one person
osw --json search ask \
  '[[Category:OSWc5d4829ed2744a219ba027171c75fa1d]][[HasActionee::Item:OSW8dca...]][[HasStatus::Item:OSWaa8d...]]'

# a substring match on the title
osw --json search ask \
  '[[Category:OSWc5d4829ed2744a219ba027171c75fa1d]][[HasLabel::~*parser*]]'
```

`--printouts` returns the property values beside each hit, which avoids one
`entity get` per task. Add `--printouts HasLabel` to get the task titles in
the same result. Do not ask for `Display_title_of`: its printout key comes
back translated and the value always reads `null`.

A printout value is never a plain string. It is a list, and each entry has a
shape that depends on the property:

| Property kind | Entry shape | Where the value is |
| --- | --- | --- |
| Page reference, such as `HasStatus` | `{"fulltext": ..., "fullurl": ...}` | `fulltext` is the page name |
| Date, such as `HasEndDateAndTime` | `{"timestamp": ..., "raw": ...}` | `timestamp` is Unix seconds |
| Text with a language, such as `HasLabel` | `{"Text": {...}, "Language code": {...}}` | `["Text"]["item"][0]` |

`truncated` in the result means further matches exist beyond the limit. Raise
`--limit` before you report a count as complete.

**"My tasks" needs the operator's own Person page name.** Take it from
`OSW_PERSON_IRI`, as described under The environment variables above.

## Resolving a person or a project

Both fields store a page name. A user gives you a name.

```
osw --json search label 'Anna Schmidt' --category Category:OSW44deaa5b806d41a2a88594f562b110e9
```

`search label` matches the displayed title exactly. It is not a substring
match. A Person is displayed as "<first name> <surname>". If it returns
nothing, try a substring search before concluding the entity is absent:

```
osw --json search ask '[[Category:OSW44deaa5b806d41a2a88594f562b110e9]][[HasLabel::~*Schmidt*]]'
```

- Exactly one match: use it, and report to the user which page name you used.
- Several matches: show every candidate with its page name and ask which one
  they mean. Do not choose yourself.
- No match: report that, and for a person see the next section.

Never invent a page name and never write a plain string into `related_to` or
`actionees`.

## Person creation is a fallback

Most OSL instances create persons and users through their own process or
workflow, and an instance usually already holds every person you need.

1. Search first, both exact and substring.
2. Only if the person is genuinely absent, ask the user whether to create one.
3. Never create a person without asking.

```
osw entity put Category:OSW44deaa5b806d41a2a88594f562b110e9 --jsondata '{
  "type": ["Category:OSW44deaa5b806d41a2a88594f562b110e9"],
  "first_name": "Anna",
  "surname": "Schmidt",
  "label": [{"text": "Anna Schmidt", "lang": "en"}]
}'
```

**Write the `label` yourself.** The Person schema derives the label from the
two name fields through a form-editor template, and that template only runs in
the browser form. A person written through the API with no `label` gets an
empty one and is then unfindable by name.

## The import loop

Process one todo at a time. Never create several tasks and then edit the file
once.

For each todo line:

1. **If the line already carries an OSW link, the task exists.** Update it or
   skip it. Never create.
2. **Create the task.**
3. **Write the link back into the file immediately**, before moving to the
   next todo.

Step 3 has to happen before step 1 of the next todo. A task that exists in OSL
but has no marker in the local file looks like a new todo on the next run, and
is created a second time. If the file edit fails, stop and report the page name
to the user rather than continuing.

## The marker format

A Markdown link appended to the todo line:

```
- [ ] Fix the parser ([OSW](https://<domain>/wiki/Item:OSW1234...))
```

`entity put` returns `urls`, so use the returned URL without changing it.

## The duplicate rule

Prefer creating a duplicate over skipping a real task. A duplicate is visible
and reversible. A skipped todo is silent and loses work.

- A link already on the line is authoritative. It always means skip or update.
- Without a link, an **exact** label match within the same project means
  update, not create.
- Anything weaker than an exact label match is a candidate. Show the
  candidates to the user and let them decide. Do not resolve it yourself.

## Troubleshooting

Nothing checks that this file and the installed `osw` package come from the
same release, although both versions are set together when a release is made.
Compare `metadata.version` in this file's frontmatter with the version that
`osw --version` prints. With the MCP server and no CLI, ask the user for the
version of the `osw` package that serves it.

If the two differ, this file can describe operations, flags or field names
that the installed package does not have, or omit ones it does have.
Reinstall with `osw skill install --force`, or update the `osl-tasks` plugin,
or update the `osw` package, until both report the same version.

If this file's frontmatter has no `metadata.version` at all, the copy is older
than the release that added that field. Reinstall it.
