# Events, durable tasks and calls

The platform carries three kinds of link between the programs of one system. It keeps
every message until it is handled, retries what fails, and draws each link on the
owner's canvas — who tells whom, about what, how much went through, what is waiting and
what failed.

| | |
|---|---|
| **event** | "this happened here; whoever cares reacts" — a topic named `thing.happened` (`booking.created`, `payment.failed`). The sender does not wait. |
| **task** | "this work must get done, even if the program restarts" — a topic named `do.thing` (`clips.cut`, `emails.send`). A program can be its own worker. |
| **call** | "I need an answer right now" — one program calls another's API through the platform, which counts it. |

**Delivery.** A message is kept in the platform's database, so it outlives any
container. It is retried after 10 s, 30 s, 2 min, 10 min, 30 min, 2 h and 6 h — eight
tries — and then marked failed where the owner sees it. One delivery at a time per
handler. Publishing the same `key` twice is one message, which is what makes a retry
safe.

## From your agent, out here

```
publish_event(system, topic, from_program, data, key)
list_events(system, topic, limit)      → done / waiting / failed, attempts, last error
```

`from_program` is required and is kept: the message is recorded as coming from that
program, exactly as its own code sending it, so the owner's canvas stays true. Pass the
slug you read from `describe_system`.

This is the tool for handing a program work: 2,000 photos to tag, a digest to rebuild, a
batch to re-run. Your laptop can close; the platform finishes it.

## Inside a program

What Bnome's agent writes, so you know what to ask for:

```python
import os, httpx
SYS, H = "http://backend:8004/_system", {"Authorization": "Bearer " + os.environ["BNOME_TOKEN"]}

httpx.get(f"{SYS}/", headers=H).json()         # siblings (slug, their API), topics, who handles what
httpx.post(f"{SYS}/handlers", headers=H, json={
    "topic": "booking.created", "path": "/api/on/booking-created",
    "name": "Count each new booking towards who is drifting"})    # the owner reads this name
httpx.post(f"{SYS}/publish", headers=H, json={
    "topic": "booking.created", "key": f"booking-{booking.id}",
    "data": {"booking_id": booking.id, "email": booking.email}})
httpx.get(f"{SYS}/call/quiet-desk/api/day", headers=H, timeout=30).json()
```

A handler is an ordinary endpoint on the program's own backend. The platform POSTs
`{"id", "topic", "data", "from", "attempt"}` to it with the program's own `BNOME_TOKEN`
as the bearer, and it must answer 2xx within 30 seconds. It may arrive twice, so the
handler keeps the message id. Work longer than 30 s is recorded for a worker, and the
handler answers at once.

Handlers are declared **once**, during the build — not on every start-up. Declaring the
same topic again updates it.

## When the platform's links are not enough

High throughput, strict order, many workers on one queue, or a queue a library expects:
the system runs its own broker as a service — Redis, RabbitMQ, NATS, Kafka, anything
([05-services.md](05-services.md)). It keeps its data in a volume and the owner sees it
on the canvas. One program calling another's address directly also works, but nothing
draws it.
