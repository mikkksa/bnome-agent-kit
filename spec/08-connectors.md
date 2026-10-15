# Other people's services

When a program should put something in the owner's Google Calendar, send from their
Gmail, update their HubSpot, write a Google Sheet or charge a card — it does not ask for
secret keys and does not build an OAuth flow. The owner signs in once in Bnome, and
every program of the system can then use that account.

**~1,600 services** through Composio: about 120 with one-click sign-in, about 1,270
where Composio's own hosted page asks for the key (so it never touches Bnome's servers),
35 that need nothing, and some that need a vendor app of their own.

**Any other API** becomes a connector the agent describes itself: a base URL, the fields
to ask for, how they authenticate (`headers`, `query` or `basic`, with `{field}`
placeholders) and a check call. The owner pastes the values once on a `/plug` page, they
are encrypted, and the secret ones never come back out. Programs then call through the
gateway. One service is one connector — the same key can serve several addresses.

## How it goes

1. The program needs a service. Its agent searches the catalogue and **requests** it.
2. The answer is `live` (use it now), `unavailable`, or `needs_owner` with a connect
   link and a line to say.
3. The agent puts that link in its reply with one line on what it turns on, and builds
   the feature so it switches on by itself once the owner has signed in.

The feature waits visibly rather than silently: *"Connect Google Calendar in Bnome and
bookings will land there"*, while everything else keeps working.

```python
import os, httpx
BASE, H = os.environ["BNOME_CONNECTORS_BASE"], {"Authorization": "Bearer " + os.environ["BNOME_TOKEN"]}

httpx.get(f"{BASE}/", headers=H).json()                       # what is connected
httpx.get(f"{BASE}/catalog", headers=H, params={"q": "notion"}).json()["items"]
httpx.get(f"{BASE}/tools/GOOGLECALENDAR_CREATE_EVENT", headers=H).json()["input"]
httpx.post(f"{BASE}/run/GOOGLECALENDAR_CREATE_EVENT", headers=H, timeout=60,
           json={"arguments": {...}}).json()                  # {"ok": true, "data": {…}}
httpx.post(f"{BASE}/request", headers=H,
           json={"toolkit": "notion", "why": "Bookings go to your Notion board"}).json()
```

Calls go from the backend, never the browser. The program saves its own row first, then
calls, then keeps the result — the event id, or the error — on that row, so nothing is
sent twice and a failed call never fails the booking it belongs to.

## From your agent

`describe_system` → `connected[]`, each with a plain-words `state`: *connected and
usable*, *waiting for the owner to sign in*, *the agent asked for it; the owner has not
signed in yet*, *signed in once, not working now*, *suggested, nobody said yes*.

If a feature is idle because a service is unconnected, that is the thing to tell the
person — with the link, not a shrug.

**An outside key does not go in `set_setting`.** Settings are for a program's own
configuration — a timezone, a feed URL. A key for an outside service belongs to a
connector, where the whole system can use it.
