# User Item Sync

Create or update OSW `User` items from the MediaWiki accounts of an OSL
instance, enriching ORCID users from the public ORCID API. The run is
idempotent and previews every change before writing.

## When to use it

OSL instances gain accounts from manual creation and from whitelisted ORCID
single sign-on (whose username is the ORCID iD). Those accounts have no
semantic `User` item until this tool reconciles them.

## Run it

```bash
uv run python examples/user_sync.py --domain your-instance.example.org --dry-run
```

Credentials are read from `accounts.pwd.yaml` (or `--cred-filepath`), the same
mechanism as `OswExpress`. Start with `--dry-run` to preview, then run without
it to write after confirming at the prompt.

To also remove data no longer wanted (disabled optional fields and
`employment_contract_status`) from existing items, add `--prune`:

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
| `--prune` | Remove disabled optional fields and `employment_contract_status` from existing items (default off; a normal run only adds). |

## What it does

1. Enumerate MediaWiki accounts, skipping bots and privileged groups
   (`bot`, `sysop`, `bureaucrat`, `interface-admin`) and MediaWiki reserved
   system usernames.
2. Enrich ORCID users from `https://pub.orcid.org/v3.0/<id>`: names and email
   always; researcher URLs and affiliations only when their flag is enabled.
3. Map each account to a proposed `User` item with a deterministic id
   (uuid5 on the ORCID iD, else the username), so re-runs are idempotent.
4. Reconcile against existing items by `username` into NEW, GAP_FILL, CONFLICT,
   REMOVE or UNCHANGED, then preview; gap-fills apply automatically and conflicts
   are resolved interactively. Removals only appear with `--prune`; a normal run
   never removes anything.
5. Store items, create `User:<username>` redirects to each item, ensure any
   linked Organization items, verify by reloading, and warn about users with no
   email.

## Data written

| Field | Policy |
| --- | --- |
| `username`, `first_name`, `surname`, `label`, `orcid` | Always (core identity). |
| `email` | Standard: always attempted; missing email is warned, not fatal; never removed. |
| `website` | Opt-in (`--with-websites`); removed from existing only with `--prune`. |
| `organization` | Opt-in (`--with-organizations`); removed from existing only with `--prune`. |
| `employment_contract_status` | Never written; removed from existing only with `--prune`. |

## Notes

- MediaWiki does not expose other users' email or real name, so ORCID is the
  only source of rich data. Non-ORCID accounts get username-based placeholder
  names, flagged in the preview.
- On a first accepted run the library autofetches schemas and may regenerate
  `src/osw/model/entity.py`; restore it if you do not want that change.
