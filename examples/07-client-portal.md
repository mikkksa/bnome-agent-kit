# A client portal on data you already have

The spreadsheet or Airtable base you run on, turned into something each client signs
into — without moving off what you have.

## The one call

```
create_app("""
My projects live in an Airtable base: clients, projects, milestones, invoices. I want
each client to sign in with a link and see only their own projects: what stage each is
at, what is waiting on them, and their invoices with whether they are paid. They can
leave a note on a milestone and I see it on my own desk. The base stays the source of
truth for my team — don't make me stop using it.
""")
```

## What comes back

Two programs: the client portal and your desk. Airtable comes in as a connector, so the
base stays where it is and the portal reads and writes through it. The agent decides
what to cache locally for speed and what to read live — and says which.

`import_app` is the other door here: if you already have an app in a public GitHub repo,
Bnome's agent ports it onto the stack and writes `IMPORT_NOTES.md` saying what changed.

## Then your agent

```python
describe_system(system)
# connected[] → airtable; data[] → whatever it mirrors locally

query_data(system, store,
  "SELECT stage, count(*) FROM projects GROUP BY stage")

query_data(system, store, """
  SELECT c.name, count(n.id) AS notes
  FROM clients c LEFT JOIN notes n ON n.client_id = c.id AND n.seen = 0
  GROUP BY c.name HAVING notes > 0
""")
```

## Sign-in is a real question, so ask it in the prompt

"A link each client signs in with" and "a password each client sets" are different
products. Say which. A secret URL is not a sign-in, and Bnome's agent is told not to
treat it as one — if the data matters, it will build an actual login or tell you it
needs to.

## Giving the portal a body of reference data

Price lists, terms, a FAQ — a file, not a code change:

```python
save_file(system, name="terms-2026.md", folder="Reference", text=terms)
```

Every program of the system reads it at `/files/Reference/terms-2026.md` at once.
