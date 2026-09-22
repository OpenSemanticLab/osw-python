# Tools

Besides the Python API, osw ships two adapters that talk to a live instance:
the `osw` command line client, and an MCP server for agent clients such as
Claude Code. Both run the same operations from one shared, SDK-free core
(`osw.service`), so a command and its matching tool behave identically. They
differ in exactly one way: only the CLI accepts filesystem paths.

## Setup

Install one of the first two; the second includes the first. Extras combine, so
one install can carry several:

```bash
uv tool install osw                    # the `osw` command
uv tool install "osw[mcp]"             # the same, plus the `osw-mcp` server
uv tool install "osw[mcp,wikitext]"    # two extras in one install
```

uv writes the console scripts to its tool bin directory, `~/.local/bin` by
default. Run `uv tool update-shell` once if that directory is not on your PATH
yet. Later, `uv tool upgrade osw` replaces the commands in place, and every
registered MCP server follows, because the command names do not change.

Two details:

- Quote the argument. `osw[mcp]` contains brackets, which zsh reads as a glob
  pattern and then refuses to run.
- uv writes `osw-mcp` to the bin directory even without the `mcp` extra, but
  that copy raises `ModuleNotFoundError` at startup. Install `osw[mcp]` before
  you register the server with a client.

<details markdown="1">
<summary>Other ways to install</summary>

```bash
pip install "osw[mcp]"          # into the active environment
uv add "osw[mcp]"               # as a dependency of the current uv project
uvx --from "osw[mcp]" osw-mcp   # run the server without installing it
```

`uvx` needs no install of its own. The MCP page shows it and the installed
`osw-mcp` command as the two registration options.

</details>

`osw[mcp]` is also part of `osw[all]`. The other extras are listed in the
[Get Started guide](../get-started.md#optional-extras).

### From a local checkout

To work on the CLI or the MCP server, install the same two commands from a
checkout in editable mode:

```bash
cd /path/to/osw-python
uv tool install --reinstall --editable ".[mcp,wikitext]"
```

`osw` and `osw-mcp` then import from `src/` in that checkout, so a source edit
takes effect the next time either command starts, with no reinstall. Both
commands follow the checked-out branch, so switching branches changes what a
registered MCP server runs. Run the install command again after a change to
`pyproject.toml`: uv re-resolves from the checkout and installs the difference.

Three things to know:

- `--reinstall` rebuilds the tool environment from scratch, so the command
  works from any previous state. It matters most in the other direction:
  returning to a released version without it keeps the editable environment and
  rewrites only the tool receipt, so receipt and environment disagree.
- On Windows, an install that has to replace the tool environment fails with
  `os error 5` while an `osw-mcp` server from it is running, because the running
  process locks the tool's `Scripts` directory. Stop the MCP clients first.
- An editable install makes the entity model regeneration described in
  [Notes for developers](mcp.md#notes-for-developers) write into your working
  tree. That section names the operations that trigger it, and says when to
  prefer `uvx` for the MCP server instead.

## In this section

| Page | Contents |
| ---- | -------- |
| [CLI](cli.md) | The `.env` quick start, the full command reference, and the global flags |
| [MCP server](mcp.md) | The tool surface, the no-filesystem-access and one-server-per-instance rules, and how to register the server with a client such as Claude Code |
| [Configuration](configuration.md) | What both adapters share: where credentials and settings come from, and the full environment-variable reference |
