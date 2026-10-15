# Seven systems, one call each

Each of these is a whole working system from one `create_app`. The prompt is the
deliverable: Bnome's agent reads it, plans what the business needs, writes the programs,
puts them live and keeps them running. Then your agent drives what it built.

Every example has the same three parts: **the one call**, **what comes back**, and
**then your agent**.

[`examples.json`](examples.json) is this list in a form an agent can read and pick from.

| | one call makes |
|---|---|
| [Price watcher → Telegram](01-price-watcher-telegram.md) | a page of watched URLs, a 30-minute check, a Telegram message when a price moves |
| [Bookings with an evening reminder](02-bookings-evening-reminder.md) | a booking page, a desk for the team, card payments, a reminder the evening before |
| [An overnight queue job](03-overnight-queue.md) | work too big for one request, handed to the durable queue and finished while you sleep |
| [A morning digest](04-morning-digest.md) | sources read on a clock, written up, delivered at 08:00 in your timezone |
| [A knowledge-base bot](05-knowledge-base-bot.md) | your documents answered over Telegram, search by meaning and by words |
| [An inbox that files itself](06-inbox-triage.md) | mail read, sorted into your own categories, a desk showing what needs a human |
| [A client portal on data you have](07-client-portal.md) | your existing spreadsheet or Airtable turned into an app each client signs into |

## How to write the one call

Say **how the business works**, not what the screens should look like. Who the people
are, what they buy or book, what you want to stop doing by hand. Bnome's agent plans the
data, the programs and the outside services from that, and tells you what only you can
give it — a Stripe key, the Gmail account mail goes from — on a connect page, never in
the chat.

Naming a mechanism is fine when you mean it: *"the reminder goes out on a schedule"*,
*"tag them in the background, not in the request"*. Naming an implementation usually
is not: let it choose SQLite or Postgres, one program or two.

## Then your agent

```
get_build_status(app_id)       until 'running' — a first build is minutes, not seconds
describe_system(system)        the map: programs, their APIs, data, topics, jobs, files
```

From there: `query_data` to see what it collected, `publish_event` to hand it work,
`schedule_job` / `job_runs` for the clock, `program_logs` when something is wrong, and
`ask_bnome_agent` for any change to the code.
