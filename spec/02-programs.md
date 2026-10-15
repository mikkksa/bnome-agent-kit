# A program, and its contract

A program is a Vite + React frontend and a FastAPI backend in one container, live at
`https://<slug>.bnome.app/`. Only `/api/*` reaches the backend; everything else is the
published frontend build.

Inside the container the program gets, in its environment:

| | |
|---|---|
| `BNOME_TOKEN` | the program's own token — every platform door below takes it |
| `BNOME_JOBS_BASE` | declare work on a clock ([04](04-jobs.md)) |
| `BNOME_AI_BASE` | the AI gateway ([07](07-ai.md)) |
| `BNOME_CONNECTORS_BASE` | outside services ([08](08-connectors.md)) |
| `http://backend:8004/_system` | events, tasks, calls, Files ([03](03-links.md), [06](06-files.md)) |

plus whatever the services of the system provide (`DATABASE_URL`, `REDIS_URL`, …) and
whatever the owner set with `set_setting`. A program reads its environment once, when it
starts, so a new setting needs a restart to take effect.

## The contract every endpoint keeps

This matters to you specifically: `describe_system` reads each program's live
`/openapi.json` and hands you the result, so the quality of these docstrings is the
quality of what your agent sees.

Bnome's agent is held to three rules:

**A real docstring, three or four sentences, for a stranger.** What it does; when
someone would call it; when they should *not* and what to use instead; what it does not
return. Two endpoints with similar names is where callers go wrong, so it says plainly
how this one differs from its neighbour.

**A typed response model.** A bare dict leaves half the contract empty.

**A small surface.** A caller's AI picks worse the more it has to choose from, and the
measured cliff is around thirty. A few endpoints that each do a whole job beat many that
each do a fragment: one `/api/day` that answers "what is happening today" beats six that
must be combined.

```python
class Booking(BaseModel):
    id: int
    client_name: str
    session_date: str          # ISO date, e.g. "2026-10-01"
    status: str                # booked | attended | cancelled
    amount_paid_cents: int

@app.post("/api/bookings", response_model=Booking)
def create_booking(payload: BookingIn):
    """Book one person into one class on one date, and take the deposit if a card is given.
    Call it when a client confirms a time; to move a booking use PATCH /api/bookings/{id}, not this.
    Fails with 409 when the class is full. Returns the new booking, not the client's other bookings."""
```

Units and format go in the field name — `amount_paid_cents`, not `amount`; ISO date
strings. Endpoints are named after what they do for the owner, not after the table they
touch.

If a program's API reads badly, say so to `ask_bnome_agent`: that is a fixable thing.

## Workers

A long-running process of a program — a queue consumer, a computation that takes
minutes — is one line in the program's `Procfile`:

```
# Publishes scheduled posts on time and answers the bot
worker: cd backend && python worker.py
```

The platform starts it with the program and starts it again whenever it stops; its
output goes to `<name>.log`, which `program_logs` reads. The comment above the line is
what the owner reads on their canvas.

A process started by hand (`nohup`, `&`, `screen`) stops at the first restart and nobody
sees it. Work on a clock is a job; work that waits for something is a worker.
