# An overnight queue job

Work too big for one request — thousands of rows, images, documents — handed to the
platform's durable queue and finished while nothing is watching.

## The one call

```
create_app("""
A photo library for my shop. I upload product photos, and each one gets a short
description, three tags and a dominant colour worked out by AI. Uploading 2,000 photos
at once must not block anything: the work goes on a queue and the page shows how many
are done, waiting and failed. I can re-run the ones that failed.
""")
```

Say it in the prompt: **the work goes on a queue**. That is a real architectural ask, and
Bnome's agent will declare a topic and a worker rather than doing it in the request.

## What comes back

One program with the upload page and the progress, a table of photos, a topic like
`photos.describe` with a handler, and a worker taking them one at a time.

## Then your agent

This is where the queue tools earn their place. Your agent can push the whole backlog
in, from out here, and close the laptop:

```python
describe_system(system)
# topics[] → photos.describe, handled by the program at /api/tasks/describe-photo

rows = query_data(system, store, "SELECT id FROM photos WHERE description IS NULL")["rows"]
for (photo_id,) in rows:
    publish_event(system, topic="photos.describe", from_program="photo-library",
                  data={"photo_id": photo_id}, key=f"describe-{photo_id}")
```

The `key` is what makes this safe to run twice: the same key is one message. Then:

```python
list_events(system, topic="photos.describe", limit=50)
# each one: done / waiting / failed, how many attempts, the last error
```

A message is kept in the platform's database, so a container restart loses nothing. A
failure is retried after 10 s, 30 s, 2 min, 10 min, 30 min, 2 h and 6 h, and only then
marked failed where you and the owner can see it.

```python
program_logs(system, "photo-library", file="worker.log", lines=60)
```
