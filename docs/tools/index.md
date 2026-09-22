# Tools

Besides the Python API, osw ships two adapters that talk to a live instance:
the `osw` command line client, and an MCP server for agent clients such as
Claude Code. Both run the same operations from one shared, SDK-free core
(`osw.service`), so a command and its matching tool behave identically. They
differ in exactly one way: only the CLI accepts filesystem paths.

## Setup

Install `osw` as a uv tool. The `mcp` extra adds the server to the same install:

```bash
uv tool install osw             # the `osw` command
uv tool install "osw[mcp]"      # the same, plus the `osw-mcp` server
```

uv writes both console scripts to its tool bin directory, `~/.local/bin` by
default. Run `uv tool update-shell` once if that directory is not on your PATH
yet, and `uv tool upgrade osw` to update them later. Quote the argument:
`osw[mcp]` contains brackets, which zsh reads as a glob pattern and then refuses
to run.

Without the `mcp` extra, uv still writes `osw-mcp` to the bin directory, but
that copy raises `ModuleNotFoundError` at startup. Install `osw[mcp]` before you
register the server with a client.

<details markdown="1">
<summary>Other ways to install</summary>

```bash
pip install "osw[mcp]"          # into the active environment
uv add "osw[mcp]"               # as a dependency of the current uv project
uvx --from "osw[mcp]" osw-mcp   # run the server without installing it
```

`uvx` needs no install of its own.
[Which command to register](mcp.md#which-command-to-register-for-the-mcp-server)
explains when to prefer it over the installed command.

</details>

`osw[mcp]` includes `osw[wikitext]`, and is itself part of `osw[all]`. The other
extras are listed in the [Get Started guide](../get-started.md#optional-extras).

## In this section

| Page | Contents |
| ---- | -------- |
| [CLI](cli.md) | The `.env` quick start, the full command reference, and the global flags |
| [MCP server](mcp.md) | The tool surface, the no-filesystem-access and one-server-per-instance rules, and how to register the server with a client such as Claude Code |
| [Configuration](configuration.md) | What both adapters share: where credentials and settings come from, and the full environment-variable reference |
