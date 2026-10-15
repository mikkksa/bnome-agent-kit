# Bookings with an evening reminder

The example the docs use, because it is the shape most small businesses need: something
clients open, something the team runs it from, and work that happens on its own.

## The one call

```
create_app("""
Bookings for my bike workshop. Clients pick a day and a slot, say what is wrong with the
bike and pay a deposit by card. My team needs a desk with today's jobs in order, where
they can change a status and add a price quote. Every client gets a reminder the evening
before their slot. Nobody but my team sees the desk.
""")
```

## What comes back

Two programs on one database: the booking page for clients, the desk for the team. A
scheduled job each evening for the reminders. It asks for the Stripe key and the Gmail
account the reminders go from, on a connect page.

Two programs, not one, because there are two audiences. One program is the right answer
when there is one — the agent decides, and says why.

## Then your agent

```python
describe_system(system)
# programs[] → the client page and the desk, each with its own API
# data[]     → bookings, slots, quotes, with their columns
# jobs[]     → "Remind tomorrow's clients", with its job id

query_data(system, store,
  "SELECT status, count(*) FROM bookings WHERE slot_date >= date('now') GROUP BY status")

run_job(reminder_job)                 # tonight's reminders, now, to see them land
job_runs(reminder_job, limit=7)       # was anyone missed this week
```

A reminder job should have a dry run; if it does, use it first:

```python
describe_system(system)   # programs[].api → is there a ?dry_run=1 on the reminder route
```

Changes that need code:

```
ask_bnome_agent(system, "A client who books twice in one evening gets two reminders. "
                        "Send one message listing both slots.")
```

## Why this one is in the docs

It is the example that starts outside an agent: someone can type that same sentence into
bnome.com and press Start. The browser path and the MCP path end in the same system.
