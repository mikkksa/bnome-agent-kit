# Price watcher → Telegram

Watch a list of product pages and get a Telegram message when a price moves.

## The one call

```
create_app("""
A price watcher for my own shopping. I paste product page URLs on a page and it checks
each one every half hour. When a price drops or rises by more than 2%, it sends me a
Telegram message with the product, the old price, the new price and the link. A page
shows every watched product with its current price and a small chart of its history.
Keep the whole price history, not just the latest.
""")
```

## What comes back

One program with a page for the list and the charts, a table of products, a table of
price points, and a scheduled job every 30 minutes. It asks for a Telegram bot token on
a connect page — the one thing only you have.

Checking a page is a fetch and a parse; it goes in the job. If a site needs a real
browser the agent will say so rather than pretend.

## Then your agent

```python
describe_system(system)
# programs[0].jobs[] → the 30-minute check, with its job id

run_job(job_id)                       # don't wait half an hour to see if it works
job_runs(job_id, limit=5)             # what each check answered

query_data(system, store, """
  SELECT p.name, min(h.price_cents)/100.0 AS low, max(h.price_cents)/100.0 AS high
  FROM products p JOIN price_points h ON h.product_id = p.id
  GROUP BY p.name ORDER BY high - low DESC
""")

program_logs(system, program, lines=40)   # when a check stops returning prices
```

Adding a site that parses differently is a code change:

```
ask_bnome_agent(system, "Prices on example.com are inside a <script type=application/ld+json> block, "
                        "not the page text. Read them from there too, and keep the existing sites working.")
```
