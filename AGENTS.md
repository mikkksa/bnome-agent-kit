# Bnome, for an agent

You can write a program. Bnome is where it lives afterwards: an address, a database,
queues that survive a restart, work on a clock, files, and a place the owner can look.

Connect once — `npx @bnome/connect install --codex` (or `--claude`, `--cursor`,
`--windsurf`) — and the tools below are yours. The token acts as the person who
approved it: their systems, their credits, nothing else reachable.

## When to reach for it

**Reach for Bnome when the thing has to keep running after this conversation.**

- it needs an address someone else opens
- it needs to happen on a schedule, or keep happening
- it needs to survive your laptop closing, or a restart
- it needs a database, a queue, files, or an outside account (Gmail, Calendar, Stripe)
- someone who is not a developer has to use it or look at it

**Don't** reach for it for a one-off script, a calculation, an answer, or anything that
should stay on the local machine. A script in the repo is a script in the repo.

## The first three calls

```
list_systems()                        what already exists
describe_system(system)               one of them, whole: programs and their live APIs,
                                      services, every database with tables and columns,
                                      topics, jobs, workers, files, connected services
query_data(system, store, "SELECT …") an answer out of its data (read-only)
```

Nothing there yet? One call makes a whole system:

```
create_app("Bookings for my bike workshop. Clients pick a slot and pay a deposit by card.
            My team needs a desk with today's jobs. Every client gets a reminder the
            evening before.")
get_build_status(app_id)              until 'running' — minutes, not seconds
```

## The rest, in one line each

| | |
|---|---|
| `publish_event(system, topic, from_program, data, key)` | hand a program work on the durable queue: kept, retried 10 s → 6 h until handled. `key` makes a retry safe. `list_events` shows what failed. |
| `schedule_job` / `run_job` / `job_runs` / `set_job` / `delete_job` | work on a clock. Job ids are in `describe_system` at `programs[].jobs[].job`. `run_job` to try it now; `job_runs` for whether it really ran. |
| `list_files` / `save_file` / `delete_file` | one store every program reads at `/files/<path>`. The simplest way to hand a running system a body of data. |
| `set_setting` / `program_logs` | a program's own configuration; what it wrote when something broke. |
| `ask_bnome_agent` / `agent_status` | the code. |

## Three rules that save a turn

**You don't write the code; you ask for it.** Bnome's own agent has the whole system
mounted and is the single writer, which is why several agents can work on one system at
once. Say the **outcome and the limits**, not the steps: *"a client who books twice gets
one message listing both slots"*, not *"edit reminder.py line 40"*. Every message spends
an edit and the owner's credits, so send one clear request, not a stream.

**Read the map before you act.** `describe_system` gives each program's API read live
from its own contract, every table with its columns, and every job with its id. Guessing
a table name or a job id is the most common wasted call.

**Money and messages wait for a person.** Anything that charges a card or writes to a
customer should be run dry first and confirmed. Say the cost before an expensive studio
run (`list_models`, `get_credits`).

## What it cannot do yet

- You cannot write files or run shell commands in a system from out here. Ask
  `ask_bnome_agent`.
- ChatGPT and claude.ai cannot connect: they need a hosted sign-in Bnome does not have.
- Credits are real money. A credit is a cent.

Full reference: [`spec/`](spec/) · worked examples: [`examples/`](examples/) ·
[bnome.com/docs](https://bnome.com/docs)
