# Work on a clock

A job is the platform calling one of a program's own routes on a schedule. Nothing runs
its own scheduler inside a container: that work would be invisible to the owner, it
would stop at the first restart, and nobody would learn it had stopped.

## From your agent

```
schedule_job(system, program, name, path, every_minutes= | daily_at=, timezone=, method=)
run_job(job_id)        → run it now, exactly as the schedule would
job_runs(job_id)       → the last runs: when, how long, what each answered
set_job(job_id, enabled=False, …)
delete_job(job_id)
```

Every job id is in `describe_system` at `programs[].jobs[].job`.

`name` is read by the owner on their canvas, so write it in their words: *"Send
tomorrow's reminders"*, not `cron_task_1`. `path` is a route on that program's own
backend.

The shortest interval is **5 minutes**; a few times an hour is usually right. `daily_at`
is `HH:MM` in the `timezone` you give.

## What the endpoint must be

- **Safe to call twice.** It may be. It must not double-send or double-charge.
- **Quick.** Long work goes on a queue for a worker ([03-links.md](03-links.md)).
- **Guarded.** The route is reachable from the internet like the rest of `/api`, so it
  runs only for `Authorization: Bearer <the program's BNOME_TOKEN>`, which is what the
  platform sends.
- **Dry-runnable** when it messages people or spends money: `?dry_run=1` does everything
  except the sending or the charge and answers with what it would have done. That is how
  it is tried before its first real run.

Nothing that spends the owner's money runs unattended without them asking for it.

## Times

Every timestamp in UTC, compared against UTC, sent as an ISO string ending in `Z`, and
converted once by the browser at the point of display. A moment recorded in UTC and
measured against a local clock comes out hours wrong, so work that just finished reads
as "3 hours ago" and the owner believes the program is stuck.

## Never claim a schedule that does not exist

A page that says "checked every hour" while nothing runs is a lie the owner will act on.
If you promise it in the interface, declare the job. And never show a "last checked"
time nobody recorded.
