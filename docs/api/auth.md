# Authentication

Credential handling for wiki and service logins. Credentials are resolved
in this order and held in memory only:

1. Credentials added programmatically (`add_credential`)
2. An existing credentials file (read-only, if one is configured)
3. The environment variables `OSW_USERNAME` / `OSW_PASSWORD`
   (`OSL_*` variants work too), e.g. loaded from a `.env` file
4. An interactive prompt (fallback `ask`)

The library never writes credentials to disk on its own.

::: osw.auth.CredentialManager
