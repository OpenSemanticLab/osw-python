---
name: osl-tasks
description: Use when importing local todo or note files into an OpenSemanticLab (OSL) wiki as Task entities, or when listing, filtering and updating tasks that already live in OSL. Covers the seven `osw task` commands and the matching MCP tools - create_task, update_task, list_tasks, list_projects, list_persons, create_person - including the duplicate rule, the link marker written back into the local file, and the fixed status and priority vocabularies.
---

# OSL task management

Read todos from local files, create them as Task entities in an OSL wiki, and
read tasks back. The operations are deliberately narrow: each one takes plain
typed parameters and returns a small flat dict. No JSON Schema is ever handed
to you, so you never have to read one.

## When to use this skill

- Importing todos or notes from a local file into OSL.
- Listing or filtering the tasks of a project or a person.
- Updating the status, priority, actionees or due date of a task.
- Writing a local Markdown view of the tasks.

## Setup

Four environment variables affect these operations. All are optional.

| Variable | Meaning |
| --- | --- |
| `OSW_PERSON_IRI` | The page name of the operator's own Person entity, for example `Item:OSW8dca...`. Required only by `list_tasks(mine=True)`. |
| `OSW_TASK_CATEGORY` | The category a newly created task is written to. |
| `OSW_PERSON_CATEGORY` | The category a newly created person is written to. |
| `OSW_PROJECT_CATEGORY` | The category used when resolving a project by name. |

Reading never uses the three category overrides. Listing and searching always
query the shared OSL core category, and MediaWiki category membership includes
the whole subclass tree. An instance that keeps its data in a local subclass,
for example a local "ISC User" subclass of Person, is therefore found without
any configuration. Set the overrides only when a newly created entity has to
land in that local subclass.

## The operations

| CLI | MCP tool | Purpose |
| --- | --- | --- |
| `osw task create` | `create_task` | Create one task. |
| `osw task update` | `update_task` | Merge fields into an existing task. |
| `osw task create-person` | `create_person` | Fallback only. See below. |

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
gets created a second time. If the file edit fails, stop and report the page
name to the user rather than continuing.

## The marker format

A Markdown link appended to the todo line:

```
- [ ] Fix the parser ([OSW](https://<domain>/wiki/Item:OSW1234...))
```

`create_task` returns both `title` and `url`, so use the returned `url`
verbatim.

## The duplicate rule

Prefer creating a duplicate over skipping a real task. A duplicate is visible
and reversible. A skipped todo is silent and loses work.

- A link already on the line is authoritative. It always means skip or update.
- Without a link, an **exact** label match within the same project means
  update, not create.
- Anything weaker than an exact label match is a candidate. Show the
  candidates to the user and let them decide. Do not resolve it yourself.

## The vocabularies

Status and priority are fixed sets of wiki items. Pass the human word; the
operation maps it to the page name.

- **Status**: `to do`, `in work`, `done`. Aliases are accepted, for example
  `todo`, `open`, `backlog`, `in progress`, `wip`, `closed`, `completed`.
  A task created without a status gets `to do`.
- **Priority**: `high`, `medium`, `low`. No aliases. A task created without a
  priority has none.

An invalid value raises an error that lists the accepted values.

**Due dates map to the task's end time.** The Task category has no due-date
property, so `due` is written to `end_date_time`. Pass `YYYY-MM-DD`, which
becomes midnight UTC, or a full ISO 8601 timestamp.

## Never guess a person or a project

`project` and each entry of `actionees` accept either a page name
(`Item:OSW...`) or a label to look up.

- No match raises an error naming the list operation to run.
- Several matches raises an error listing every candidate with its page name.

Show that list to the user and ask which one they mean. Do not pick one
yourself. Pass the page name once the user has chosen.

A label search matches a substring, so exactly one match is accepted without
any further question, even when it is not the entity the user meant.
`create_task` and `update_task` return the resolved page names in
`related_to` and `actionees`. Report those names to the user.

## Person creation is a fallback

Most OSL instances create persons and users through their own process or
workflow, and an instance usually already holds every person you need.

1. Only if the person is genuinely absent, ask the user whether to create one.
2. Create it with `create_person` and its `first_name` and `surname`.

Never create a person without asking.

## Worked example

```
# create it
osw task create "Fix the parser" --project "Item:OSW3660..." \
  --status "in work" --prio high --due 2026-12-31

# later, mark it done
osw task update Item:OSW1234... --status done
```

`update` changes only the fields you pass. A field you leave out keeps its
stored value. To clear a field, edit the entity with `osw entity put`.

`project` and `actionees` replace the stored list, they do not add to it.
Passing one actionee removes every other actionee the task had.
