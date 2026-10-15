# A system

A business on Bnome is a **system**, not an app: a few programs that share one database
and one file store, each live at its own address, with the jobs and queues that keep
them in step.

```
a system
├── a program          clients open it            https://<slug>.bnome.app/
├── a program          the owner's desk           https://<slug>.bnome.app/
├── services           Postgres, Redis, … (only if the system declared them)
├── Files              one store, every program reads it at /files/<path>
├── topics             durable queues and events between the programs
├── jobs               work on a clock
└── one agent          writes all the code, keeps the parts consistent
```

**Up to 8 programs** per system. How many a system needs is the agent's decision, not a
template: one program is often right, and a second appears when there is a second
audience (clients and the team) or a second job.

**One database, or several — the agent chooses.** Often it is a SQLite file inside the
program that owns it, and the others call that program or hear its events. When the
product needs more, the agent declares Postgres as a service (see
[05-services.md](05-services.md)). There is no mandatory table and no preset schema.

**Addresses.** Every program is live at `https://<slug>.bnome.app/` from its first
build; `set_slug` renames it. A paid plan can put a program on a custom domain.

**Builds are published, not hot.** A program's frontend is a production build that the
platform publishes after it opens every page in a browser and finds no errors. People
keep the version they had until a new one comes up clean.

**Sleep.** On the free plan a system nobody opened for a day sleeps and wakes in a few
seconds on the next visit, job, message or API call, with all its data. Paid systems
never sleep.

**Who writes the code.** One agent per system, reached with `ask_bnome_agent`. One
writer is the point: several of your own agents can work on the same system at once
through the other tools without ever conflicting over a file.

## Reading one

```
list_systems()              → id, name, programs, whether one agent runs it
describe_system(system)     → the whole map
```

`describe_system` is the orientation call. It gives, for one system:

- `programs[]` — `program` (id), `slug`, `name`, `status`, `url`, `health`,
  `api[]` read live from the program's own contract, `jobs[]` each with its `job` id,
  `workers[]`, and the names (never values) of its settings
- `services[]` — what it declared, its image, and whether it runs
- `data[]` — every store, with `tables[]`, their row counts and their columns
- `topics[]` — who publishes, who handles, what is waiting or failed
- `links[]` — how the programs are actually linked, and how much went through
- `files` — room used, and the folders
- `connected[]` — outside services, each with a plain-words `state`
- `how` — one line per mechanism, pointing at the tool that drives it

Everything names a program by its **slug**, so what you read you can pass back.
