# A morning digest

Sources read on a clock, written up, delivered before you are at your desk.

## The one call

```
create_app("""
A morning news desk for my industry. It reads these RSS feeds and these three subreddits
through the day, keeps what is actually new, and at 08:00 Europe/Berlin sends me one
Telegram message: five items, each a line on what happened and why it matters, with the
link. A page shows the archive of past digests and lets me mark an item as useless, so
it picks better.
""")
```

## What comes back

One program, a table of items, a table of digests, a job on the hour to collect and a
job at 08:00 to write and send. It uses the AI gateway for the picking and the writing —
no API key of yours. It asks for a Telegram bot token.

## Then your agent

```python
describe_system(system)
# jobs[] → "Collect new items" hourly, "Send the morning digest" daily at 08:00

job_runs(digest_job, limit=7)         # did it go out every morning this week
run_job(digest_job)                   # rebuild today's, now

query_data(system, store, """
  SELECT source, count(*) AS items, sum(used) AS made_the_digest
  FROM items WHERE created_at > date('now','-7 day') GROUP BY source ORDER BY items DESC
""")
```

## The failure worth knowing about

A model provider can fail behind an HTTP 200 — an error in the body, an empty answer, a
truncated one. Bnome's gateway turns those into real errors (502 / 400 / 429) and does
not charge for an empty answer, but a program still has to decide what to do about a
long outage.

So for anything that must arrive, ask for the retry explicitly:

```
ask_bnome_agent(system, "When the digest fails, tell me on Telegram and try again every "
                        "15 minutes, up to 5 times. Don't send a half-written digest.")
```

Then `job_runs` tells you which mornings needed the retry.
