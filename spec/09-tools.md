# The tools

Generated from `mcp-server/mcp_server.py`, so this is what the server really exposes.
Every tool takes the caller's own token and reaches only their own account.

## The system

Where every session starts. Everything names a program by its slug, so what you read you can pass back.

**`list_systems()`**  
List the user's systems (spaces): each one's id, name and the programs it runs.

**`describe_system(system: str)`**  
Everything one system has, in one read — the map to work from.

## Its data

Read-only. Store ids and table columns come from `describe_system` at `data[]`.

**`read_table(system: str, store: str, table: str, limit: int = 50, offset: int = 0, search: str = '', sort: str = '', newest_first: bool = False)`**  
Read rows from any table a system keeps — a program's own database, or a database service.

**`query_data(system: str, store: str, sql: str, limit: int = 200)`**  
Ask a system's data a question in SQL. Read-only: one SELECT, nothing is changed.

## Its queues

Durable: kept, delivered to every handler, retried 10 s → 6 h. See [03-links.md](03-links.md).

**`publish_event(system: str, topic: str, from_program: str, data: dict | list | str | int | float | bool | None = None, key: str | None = None)`**  
Put a message on one of a system's topics — the platform's durable queue.

**`list_events(system: str, topic: str = '', limit: int = 30)`**  
What a system put on its topics lately, and how each delivery went (done, waiting, failed, retries).

## Its clock

Job ids are in `describe_system` at `programs[].jobs[].job`. See [04-jobs.md](04-jobs.md).

**`schedule_job(system: str, program: str, name: str, path: str = '/api/job', every_minutes: int | None = None, daily_at: str | None = None, timezone: str = 'UTC', description: str | None = None)`**  
Have the platform call one of a program's own routes on a clock — a scheduled job.

**`run_job(job_id: str)`**  
Run one of a program's scheduled jobs right now, exactly as the schedule would call it.

**`job_runs(job_id: str, limit: int = 20)`**  
The last runs of a scheduled job: when each ran, how long it took, and what it answered.

**`set_job(job_id: str, enabled: bool | None = None, every_minutes: int | None = None, daily_at: str | None = None, path: str | None = None, name: str | None = None)`**  
Change or switch off a scheduled job.

**`delete_job(job_id: str)`**  
Remove a scheduled job. set_job(enabled=False) stops a job without removing it.

## Its files

One store every program of the system reads at `/files/<path>`. See [06-files.md](06-files.md).

**`list_files(system: str, folder: str = '', search: str = '', trash: bool = False)`**  
A system's Files: one folder, or everything matching a search, with the room left on the plan.

**`save_file(system: str, name: str, folder: str = '', text: str | None = None, from_url: str | None = None)`**  
Put a file into a system's Files, where its programs read it at /files/<folder>/<name>.

**`delete_file(system: str, file: str)`**  
Put a file of a system's Files in the trash, where it stays 30 days and the owner can restore it.

## Its programs

A setting is the program's own configuration. An outside service's key goes in a connector instead.

**`set_setting(system: str, program: str, key: str, value: str, secret: bool = True)`**  
Put a setting or a key into a program's environment, where its code reads it as os.environ[KEY].

**`program_logs(system: str, program: str, file: str = '', lines: int = 80)`**  
The last lines a program wrote — its backend, its last frontend build, each of its workers.

## Its code

One writer, so your agents never conflict. Say the outcome and the limits, not the steps. Spends an edit and the owner's credits.

**`ask_bnome_agent(system: str, message: str)`**  
Send a request to Bnome's own agent — the one that writes and ships this system's code — to build or change something.

**`agent_status(system: str, limit: int = 6)`**  
What Bnome's own agent is doing in a system, and what it last said.

## Building and bringing over

The other way in: Bnome's agent plans and writes the whole thing.

**`create_app(prompt: str, name: str | None = None)`**  
Create a brand-new Bnome app from a natural-language prompt.

**`import_app(source_url: str, ref: str | None = None, subdir: str | None = None, name: str | None = None, instructions: str | None = None)`**  
Import an existing app from a public GitHub repository and put it live on Bnome.

**`modify_app(workspace_id: str, prompt: str)`**  
Modify an existing running app with a natural-language change request.

**`get_build_status(app_id: str)`**  
Check an app's current build/run status.

**`list_my_apps()`**  
List all apps owned by the authenticated Bnome user (id, name, status, live_url).

**`set_slug(app_id: str, slug: str)`**  
Set a human-readable vanity subdomain for an app -> https://<slug>.bnome.app/.

## Credits

Building and running spend the owner's Bnome credits. A credit is a cent.

**`get_credits()`**  
The user's Bnome credit balance: remaining, included, purchased, used and plan tier.

