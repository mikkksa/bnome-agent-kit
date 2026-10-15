---
name: bnome
description: Ship something that keeps running — a program at a real address, with a database, durable queues, scheduled work, files and outside accounts (Gmail, Calendar, Stripe). Use when the user wants a tool, app, bot, dashboard, portal or automation that has to outlive this conversation, be opened by someone else, run on a schedule, or survive a restart; or when they mention Bnome, or ask about a system they already have there. Not for one-off scripts or local work.
---

# Bnome

Bnome is where software an agent builds keeps running. Connect it once with
`npx @bnome/connect install --claude`, and the `mcp__bnome__*` tools are available.

The token acts as the user: their systems, their credits, nothing else reachable.

## Decide first: does this need to keep running?

Yes, if it needs an address someone opens, a schedule, a database, a queue, files, an
outside account, or a non-developer looking at it. Then use Bnome.

No, if it is a one-off script, a calculation, or something that belongs in the user's
repo. Then just write it locally. Don't put a shell script on a platform.

## Orient before you act

```
list_systems()                          what the user already has
describe_system(system)                 the whole map, in one read
```

`describe_system` gives, for one system: every program with its slug, address, health
and **its API read live from its own contract**; the services it declared; every
database with its tables **and their columns**; its topics, with what is waiting or
failed; every job **with its id**; its workers, files and connected services; and a
`how` field naming the tool for each mechanism.

Read it before acting. Guessing a table name or a job id is the most common wasted call.
Everything names a program by its slug, so what you read you can pass straight back.

## Making something new

One `create_app` call makes a whole system — Bnome's agent plans the data, the programs
and the outside services, writes them, and puts them live.

Write the prompt as **how the business works**, not what the screens look like. Naming a
mechanism is fine when you mean it ("the work goes on a queue", "a reminder the evening
before"); naming an implementation usually is not — let it choose SQLite or Postgres,
one program or two.

```
create_app("…")
get_build_status(app_id)       until 'running'. Minutes, not seconds — tell the user that.
```

Seven worked prompts, each a whole system, are in `examples/` of the bnome-agent-kit
repo, with `examples/examples.json` for picking one.

## Driving what exists

| want | call |
|---|---|
| an answer out of the data | `query_data(system, store, "SELECT …")` — read-only. `read_table` to browse. |
| hand a program work in bulk | `publish_event(system, topic, from_program, data, key)` — durable, retried 10 s → 6 h. Always pass `key`, so a repeat is one message. Then `list_events`. |
| run on a clock | `schedule_job`, and `run_job` to try it now rather than waiting. `job_runs` for whether it really ran and what it answered. |
| give the system data | `save_file(system, name, folder, text=…)` — every program reads it at `/files/<folder>/<name>` at once. |
| something is broken | `program_logs(system, program)`, `list_events`, `job_runs`. In that order. |
| change the code | `ask_bnome_agent(system, "…")`, then `agent_status(system)`. |

## Asking for code

You are not the writer. Bnome's own agent has the system mounted and is the single
writer — which is why several agents can work on one system without conflicting.

Say the **outcome and the limits**, not the steps:

- good: *"A client who books twice in one evening gets two reminders. Send one message
  listing both slots."*
- bad: *"Open reminder.py and change the loop on line 40."*

Every message spends an edit and the user's credits and takes minutes, so send one clear
request and then poll `agent_status` — don't send a stream of corrections.

## Care

- **Money and messages wait for a person.** Before anything that charges a card or
  writes to a customer, check for a dry run and confirm with the user.
- **Say the cost** before an expensive studio run: `list_models`, `get_credits`. A credit
  is a cent.
- **A connector that says "waiting for the owner to sign in"** is not a bug to debug. The
  feature is idle on purpose; give the user the link.
- **An outside service's key never goes in `set_setting`** — that is for a program's own
  configuration. Keys belong to connectors, where the whole system can use them.

## Not yet

No writing files or running shell commands in a system from out here — ask the agent.
ChatGPT and claude.ai cannot connect; agents that read a token can.
