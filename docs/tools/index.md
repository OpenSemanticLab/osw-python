# Tools

Besides the Python API, osw ships two adapters that talk to a live instance:
the `osw` command line client, and an MCP server for agent clients such as
Claude Code. Both run the same operations from one shared, SDK-free core
(`osw.service`), so a command and its matching tool behave identically. They
differ in exactly one way: only the CLI accepts filesystem paths.

## Setup

Install one of the two; the second includes the first:

```bash
uv tool install osw             # the `osw` command
uv tool install "osw[mcp]"      # the same, plus the `osw-mcp` server
```

<details markdown="1">
<summary>Other ways to install</summary>

```bash
pip install "osw[mcp]"          # into the active environment
uv add "osw[mcp]"               # as a dependency of the current uv project
uvx --from "osw[mcp]" osw-mcp   # run the server without installing it
```

`uvx` is what the registration examples further down use, so the server needs
no install of its own.

</details>

`osw[mcp]` is also part of `osw[all]`. The other extras are listed in the
[Get Started guide](../get-started.md#optional-extras).

## In this section

| Page | Contents |
| ---- | -------- |
| [CLI](cli.md) | The `.env` quick start, the full command reference, and the global flags |
| [MCP server](mcp.md) | The tool surface, the no-filesystem-access and one-server-per-instance rules, and how to register the server with a client such as Claude Code |
| [Configuration](configuration.md) | What both adapters share: where credentials and settings come from, and the full environment-variable reference |
