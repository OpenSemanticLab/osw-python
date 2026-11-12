# User Item Sync

Create or update OSW `User` items from the MediaWiki accounts of an OSL
instance, enriching ORCID users from the public ORCID API. The run is
idempotent and previews every change before writing.

This is a Python script built on the osw library. It is not a command of the
`osw` CLI and not an MCP tool, see [Tools](index.md). It runs from a source
checkout, because `examples/` is not part of the installed package.

## When to use it

OSL instances gain accounts from manual creation and from whitelisted ORCID
single sign-on (whose username is the ORCID iD). Those accounts have no
semantic `User` item until this tool reconciles them.

## Run it

```bash
uv run python examples/user_sync.py --domain your-instance.example.org --dry-run
```

The script reads the credential file given by `--cred-filepath`, otherwise
`accounts.pwd.yaml` in the working directory, otherwise the file named by the
`OSW_CRED_FILEPATH` environment variable. It does not read a `.env` file.
`--domain` falls back to the `OSW_DOMAIN` environment variable. See
[Credentials](configuration.md#credentials) for the file format. Start with
`--dry-run` to preview, then run without it to write after confirming at the
prompt.

To also clean up existing items, add `--prune`. Without it, the sync never
writes `employment_contract_status` and never removes anything. With it,
`employment_contract_status` is removed from the stored jsondata of existing
items. `website` and `organization` are overwritten with an empty list, unless
`--with-websites` or `--with-organizations` enables them. This happens in a
second edit of the page's jsondata after the store. The sync decides from the
stored jsondata, not from the loaded item, which shows the model default for
`employment_contract_status`. A second `--prune` run therefore changes nothing:

```bash
uv run python examples/user_sync.py --domain your-instance.example.org --prune --dry-run
```

Users whose ORCID record exposes no email are listed in a warning at the end of
the run; a missing email never fails the sync.

### Options

By default the tool syncs both ORCID and MediaWiki-native accounts and writes
only core identity plus email.

| Flag | Effect |
| --- | --- |
| `--domain` | Target OSL domain. |
| `--cred-filepath` | Path to `accounts.pwd.yaml`. |
| `--dry-run` | Preview only; never writes. |
| `--auto-apply` | Non-interactive: apply creates, gap-fills and removals; keep existing on conflicts. |
| `--limit N` | Process at most N accounts (testing). |
| `--orcid-only` | Only ORCID-username accounts (excludes `--mw-only`). |
| `--mw-only` | Only non-ORCID (MediaWiki-native) accounts (excludes `--orcid-only`). |
| `--include-system` | Do not skip MediaWiki reserved system accounts. |
| `--no-redirects` | Do not create `User:` redirect pages. |
| `--with-websites` | Also store ORCID researcher URLs (opt-in). |
| `--with-organizations` | Also create and link Organization items from ORCID affiliations (opt-in). |
| `--with-extras` | Enable both websites and organizations. |
| `--include-blocked` | Do not skip blocked MediaWiki accounts. |
| `--prune` | Remove `employment_contract_status` from the stored jsondata of existing items, and overwrite `website` or `organization` with an empty list when their opt-in flag is not given, in a second edit of the page's jsondata after the store (default off; a normal run never writes `employment_contract_status` and never removes anything). |

## What it does

1. Enumerate MediaWiki accounts, skipping blocked accounts (unless
   `--include-blocked` is set; the User item of a skipped blocked account is
   left unchanged), bots and privileged groups
   (`bot`, `sysop`, `bureaucrat`, `interface-admin`) and MediaWiki reserved
   system usernames. Accounts whose username is an exact ORCID iD are exempt
   from the group filter (so a person's own admin account is synced); other
   accounts, such as `<orcid>@bot`, are still excluded by their groups.
2. Enrich ORCID users from `https://pub.orcid.org/v3.0/<id>`: names and email
   always; researcher URLs and affiliations only when their flag is enabled.
3. Map each account to a proposed `User` item with a deterministic id
   (uuid5 on the ORCID iD, else the username), so re-runs are idempotent.
4. Reconcile against existing items. Existing items are found by `username`
   across all `User` items. An item whose deterministic page already exists is
   updated and not created again. Each user gets one of four categories: NEW,
   GAP_FILL, CONFLICT or UNCHANGED. Each changed field has one of three
   statuses: GAP_FILL, CONFLICT or REMOVE. The preview shows a removed field as
   `-field`. A user with only gap-fills or removals is GAP_FILL. Gap-fills apply
   automatically and conflicts are resolved interactively. Removals appear only
   with `--prune`; a normal run never removes anything.
5. Store items, create `User:<username>` redirects to each item, ensure any
   linked Organization items, verify by reloading, and warn about users with no
   email.

## Data written

| Field | Policy |
| --- | --- |
| `username`, `first_name`, `surname`, `label`, `orcid` | Always (core identity). |
| `email` | Standard: always attempted; missing email is warned, not fatal; never removed. |
| `website` | Opt-in (`--with-websites`); without that flag, on existing items overwritten with an empty list only with `--prune`, in a second jsondata edit after the store. |
| `organization` | Opt-in (`--with-organizations`); without that flag, on existing items overwritten with an empty list only with `--prune`, in a second jsondata edit after the store. |
| `employment_contract_status` | Never written without `--prune`; with `--prune`, removed from the stored jsondata of existing items in a second jsondata edit after the store. |

## Notes

- MediaWiki does not expose other users' email or real name, so ORCID is the
  only source of rich data. Non-ORCID accounts get username-based placeholder
  names, flagged in the preview. Placeholder names are written only for new
  items and are never proposed for an existing item.
- In a source checkout (for developers), the first accepted run autofetches
  schemas and may regenerate `src/osw/model/entity.py`. Restore it if you do not
  want that change.
