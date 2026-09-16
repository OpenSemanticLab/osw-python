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

### Options

| Flag | Effect |
| --- | --- |
| `--domain` | Target OSL domain. |
| `--cred-filepath` | Path to `accounts.pwd.yaml`. |
| `--dry-run` | Preview only; never writes. |
| `--yes` | Non-interactive: create and gap-fill, keep existing on conflicts. |
| `--limit N` | Process at most N accounts (testing). |
| `--orcid-only` | Only accounts whose username is an ORCID iD. |
| `--include-system` | Do not skip MediaWiki reserved system accounts. |
| `--no-redirects` | Do not create `User:` redirect pages. |
| `--no-organizations` | Do not link ORCID affiliations to Organization items. |

## What it does

1. Enumerate MediaWiki accounts, skipping bots and privileged groups
   (`bot`, `sysop`, `bureaucrat`, `interface-admin`) and MediaWiki reserved
   system usernames.
2. Enrich ORCID users from `https://pub.orcid.org/v3.0/<id>` (names, public
   email, websites, employment or affiliation).
3. Map each account to a proposed `User` item with a deterministic id
   (uuid5 on the ORCID iD, else the username), so re-runs are idempotent.
4. Reconcile against existing items by `username` into NEW, GAP_FILL, CONFLICT
   or UNCHANGED, then preview and resolve conflicts interactively.
5. Store items, create `User:<username>` redirects to each item, ensure linked
   Organization items, and verify by reloading.

## Notes

- MediaWiki does not expose other users' email or real name, so ORCID is the
  only source of rich data. Non-ORCID accounts get username-based placeholder
  names, flagged in the preview.
- On a first accepted run the library autofetches schemas and may regenerate
  `src/osw/model/entity.py`; restore it if you do not want that change.
