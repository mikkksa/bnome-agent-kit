# What a Bnome system is

Enough for an agent to work without guessing. Written from the guides the platform
hands its own build agent, so this is the real contract, not a brochure.

| | |
|---|---|
| [01-system.md](01-system.md) | a system: programs, addresses, the database they share, who writes the code |
| [02-programs.md](02-programs.md) | a program, and the contract every endpoint keeps so other programs and agents can call it |
| [03-links.md](03-links.md) | events, durable tasks (queues) and calls between programs |
| [04-jobs.md](04-jobs.md) | work on a clock |
| [05-services.md](05-services.md) | Postgres, Redis, anything from a public image — `compose.yaml` and the `x-bnome` keys |
| [06-files.md](06-files.md) | one file store the whole system reads |
| [07-ai.md](07-ai.md) | AI inside a program, with no keys of its own |
| [08-connectors.md](08-connectors.md) | Gmail, Calendar, Stripe, ~1,600 more, and any other API |
| [09-tools.md](09-tools.md) | the MCP tools, one line each |

**Read this first.** Two different things write code here, and mixing them up is the
main way an agent wastes a turn:

- **Bnome's own agent** lives inside the system with every program's folder mounted. It
  writes the code, declares the handlers and jobs, starts the services, and publishes.
  You reach it with `ask_bnome_agent`. Everything in 01–08 describes what *it* builds.
- **Your agent**, out here, drives the running system with the MCP tools in 09: it reads
  the map and the data, puts work on the queues, sets the clock, keeps files, changes
  settings, and reads logs.

So: ask for the thing, then run it. Say the outcome and the limits to `ask_bnome_agent`,
not the steps — it is an engineer, not a compiler.
