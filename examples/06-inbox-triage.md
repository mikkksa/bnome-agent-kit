# An inbox that files itself

Mail read as it arrives, sorted into categories you chose, with a desk showing only what
needs a person.

## The one call

```
create_app("""
Triage for my support inbox. It reads new mail from my Gmail every 10 minutes and sorts
each one into: a new order, a question about an existing order, a complaint, a supplier,
or noise. A desk shows what is waiting, newest first, with the original mail and a
suggested reply I can edit and send from my own address. It never sends anything by
itself. Each sort keeps the reason, so I can see why it chose.
""")
```

"It never sends anything by itself" is worth saying out loud. Anything that spends money
or speaks to a customer should wait for a person unless you say otherwise.

## What comes back

One program, a table of messages with their category, reason and state, a 10-minute job,
and the desk. Gmail arrives as a connector: the agent asks for it, you sign in once, and
no key goes anywhere near the code.

## Then your agent

```python
describe_system(system)
# connected[] → gmail, with a plain-words state.
#   "the agent asked for it; the owner has not signed in yet" means the feature is idle —
#   tell the person, with the link, rather than debugging the program.

query_data(system, store, """
  SELECT category, count(*) FROM messages
  WHERE received_at > date('now','-7 day') GROUP BY category ORDER BY 2 DESC
""")

query_data(system, store,
  "SELECT subject, category, reason FROM messages ORDER BY received_at DESC LIMIT 20")
```

Reading the reasons is how you tune it. When a category is consistently wrong, that is
one sentence to the agent:

```
ask_bnome_agent(system, "Anything from a @supplier-domain.com address is a supplier even when "
                        "it reads like a complaint. Right now those land in complaints.")
```

## Re-sorting the backlog

A new category means the old mail should be re-read. That is the queue, not a migration:

```python
rows = query_data(system, store,
  "SELECT id FROM messages WHERE category = 'noise' AND received_at > date('now','-30 day')")["rows"]
for (mid,) in rows:
    publish_event(system, topic="messages.sort", from_program="inbox-triage",
                  data={"message_id": mid}, key=f"resort-{mid}")
list_events(system, topic="messages.sort", limit=50)
```
