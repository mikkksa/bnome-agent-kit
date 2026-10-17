# Bnome plugin for Claude

Bnome builds and runs software that keeps working when your laptop is closed: apps with their own
databases, durable queues, scheduled jobs and files, live at their own address. This plugin gives
Claude two ways to use it. Bnome's own agent can build or change an app from a plain description
(`create_app`, `import_app`, `modify_app`). Or Claude works on a running system directly: it reads
the system's map and data, puts work on its queues, schedules jobs, manages its files and settings,
reads its logs, and hands code changes to Bnome's agent (`ask_bnome_agent`).

## Install

In Claude Code:

```
/plugin install bnome --marketplace mikkksa/bnome-agent-kit
```

## What it contains

- **A skill** (`skills/bnome/SKILL.md`) that tells Claude when Bnome fits — something that must keep
  running, be opened by someone else, or run on a schedule — and how to use the tools well.
- **One MCP server**, Bnome's hosted server at `https://mcp.bnome.com/mcp`. Nothing runs on your
  machine.

## What it sends where

- Claude calls `https://mcp.bnome.com/mcp`, which forwards each call to Bnome's API at
  `https://bnome.com/api` with your sign-in. Only the arguments of the tool Claude calls are sent:
  for example the description of an app to build, an SQL query, or a file you ask it to save.
- Sign-in is OAuth: the first call opens a Bnome page where you sign in and allow access. You can
  withdraw access at any time with **Sign out AI agents** on your Bnome profile.
- Building apps and running them spend your Bnome credits; `get_credits` shows the balance.
- The plugin reads nothing else from your computer or your conversations.

Privacy policy: https://bnome.com/privacy · Terms: https://bnome.com/terms · Docs: https://bnome.com/docs#mcp

## License

MIT, see [LICENSE](LICENSE). Bnome itself is a hosted service and is not open source.
