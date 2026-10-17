# Bnome agent kit

**The runtime your AI agent ships to.**

Your agent can already write a program. It has nowhere to put it that is still running
next week — with an address, a database, a queue that survives a restart, work on a
clock, files, and somewhere the owner can look.

[Bnome](https://bnome.com) is that place, and this repo is everything an agent needs to
use it: the MCP server, the installer, a spec of what a Bnome system is, worked
examples, and a skill you can drop into Claude Code or Codex.

```bash
npx @bnome/connect install --claude     # or --cursor, --codex, --windsurf
```

That opens bnome.com, you press **Approve**, and your agent has the tools below. The
token acts as you: your systems, your credits, nothing else reachable. Take it back any
time with **Sign out AI agents** on your profile.

---

## Two ways to work, and they mix

**Bnome builds it for you.** `create_app` with a sentence. Bnome's own agent plans the
system, writes the programs, puts them live and keeps them running.

**Your agent builds on Bnome.** `describe_system` gives it the whole map — the programs
and their live APIs, the services the system declared, every database with its tables,
its topics, its schedules, its files. From there it reads the data, hands programs work
through the durable queue, sets the clock, keeps files, and asks Bnome's agent for code
when code is what is needed.

The code has one writer — Bnome's own agent, reached with `ask_bnome_agent` — so several
of your agents can work on one system at once without overwriting each other.

## The tools

| | |
|---|---|
| `list_systems` · `describe_system` | every system, then one of them whole: programs and their live APIs, services, databases with tables and columns, topics with what is waiting or failed, jobs, workers, files, connected services |
| `read_table` · `query_data` | read any table; ask in SQL, read-only |
| `publish_event` · `list_events` | the durable queue: kept, delivered to every handler, retried 10 s → 6 h until it is handled |
| `schedule_job` · `run_job` · `set_job` · `job_runs` · `delete_job` | work on a clock, and whether it actually ran |
| `list_files` · `save_file` · `delete_file` | one store every program of the system reads at `/files/<path>` |
| `set_setting` · `program_logs` | a program's own settings and keys; what it wrote when something broke |
| `ask_bnome_agent` · `agent_status` | have Bnome's agent write and ship the code |
| `create_app` · `import_app` · `modify_app` · `get_build_status` · `list_my_apps` · `set_slug` | build from a sentence, or bring a public GitHub repo over |
| `get_credits` | the owner's credit balance; building and running spend it |

Full reference: [`spec/09-tools.md`](spec/09-tools.md).

## What is in here

| | |
|---|---|
| [`spec/`](spec/) | what a Bnome system is, so an agent works without guessing: programs and their contract, events and durable tasks, schedules, services it can declare, Files, the AI gateway, outside services |
| [`examples/`](examples/) | seven systems an agent ships in one call, each with the exact prompt and the follow-up calls — [`examples.json`](examples/examples.json) is the same list for an agent to read |
| [`AGENTS.md`](AGENTS.md) | drop-in instructions for Codex and any agent that reads AGENTS.md: when to reach for Bnome, and the first three calls |
| [`.claude/skills/bnome/SKILL.md`](.claude/skills/bnome/SKILL.md) | the same as a Claude Code skill |
| [`mcp-server/`](mcp-server/) | the MCP server itself — a thin wrapper over `bnome.com/api`, holding no logic of its own. Run your own against the same API if you prefer |
| [`connect-cli/`](connect-cli/) | the source of `@bnome/connect`, the installer |

## Start in three calls

```
list_systems()                       → the systems you have
describe_system(system)              → everything one of them is
query_data(system, store, "SELECT …")  → an answer out of its data
```

With nothing there yet, start with `create_app("…")` — see [`examples/`](examples/) for
prompts that produce a whole working system.

## Honestly

- **This kit is MIT. Bnome itself is not open source** — it is a hosted platform, and
  these tools talk to it. Everything here is free to read, fork, and point at your own
  deployment if you run the server yourself.
- **ChatGPT and claude.ai cannot connect yet.** They take an external MCP server only
  through a hosted sign-in (OAuth), which Bnome does not have. Agents that read a token
  — Claude Code, Cursor, Codex, Windsurf — work today.
- **Your agent cannot write code into a system from out here yet.** It asks Bnome's
  agent, which has the whole system mounted. Direct file and shell access from outside is
  the next thing being built.
- Running a system costs credits. A credit is a cent; see [bnome.com/pricing](https://bnome.com/pricing).

## Links

- [bnome.com](https://bnome.com) · [docs](https://bnome.com/docs) · [what agents do with it](https://bnome.com/docs#examples) · [pricing](https://bnome.com/pricing)
- MCP endpoint: `https://mcp.bnome.com/mcp`
- [llms.txt](https://bnome.com/llms.txt)

MIT — see [LICENSE](LICENSE).
