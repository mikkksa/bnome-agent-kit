"""
Bnome MCP server — thin wrapper over the existing Bnome REST API.

Design: this process holds NO business logic. Every tool forwards the caller's
Bearer token (read from the incoming MCP request headers) to https://bnome.com/api
and returns the JSON.

Two ways in. Bnome's own build agent makes or changes an app (create_app, import_app,
modify_app; poll get_build_status). Or the caller works on a running system directly:
its map, data, durable queues, schedules, files, settings and logs, and hands code
changes to Bnome's agent (ask_bnome_agent).

The studio tools (images, video, music, transcripts, clips, film, try-on) were taken out
on 2026-10-17; they live on in Hedgehog. Their code is at commit 4461b7b.

Run:  python mcp_server.py            (http transport, port 8010, path /mcp)
Auth: OAuth 2.1, as the MCP authorization spec has it. This server is the protected resource: a request
without a token Bnome's API takes gets 401 pointing at this server's protected-resource metadata, which
names the site as the authorization server (backend routers/oauth.py). Clients that sign in there
(claude.ai, ChatGPT, Claude Code) and agents `npx @bnome/connect` set up send the same kind of token:
Authorization: Bearer <agent token>. BNOME_MCP_URL is this server's public address.
"""
import os
import asyncio
import hashlib
import time
from typing import Literal
from urllib.parse import quote, urlparse

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, RemoteAuthProvider, TokenVerifier
from fastmcp.server.dependencies import get_http_headers
from pydantic import AnyHttpUrl
from starlette.routing import Route

API_BASE = os.environ.get("BNOME_API_BASE", "https://bnome.com/api").rstrip("/")
SITE_BASE = API_BASE.rsplit("/api", 1)[0]
HOST = os.environ.get("BNOME_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("BNOME_MCP_PORT", "8010"))
# This server's public address: the resource MCP clients sign in for (https://mcp.bnome.com/mcp).
MCP_URL = urlparse(os.environ["BNOME_MCP_URL"])


class BnomeTokens(TokenVerifier):
    """A bearer token is good when Bnome's API takes it: an agent token, from the OAuth consent page or
    `npx @bnome/connect`, or an account's own session. The API's yes is kept 30 seconds so a busy session
    doesn't ask on every message; every tool call still sends the token to the API, which checks it again,
    so «Sign out AI agents» stops the tools at once and this door within the 30 seconds."""

    KEEP_SECONDS = 30

    def __init__(self):
        super().__init__(required_scopes=["agent"])
        self._known: dict[str, tuple[float, AccessToken]] = {}

    async def verify_token(self, token: str) -> AccessToken | None:
        key = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        known = self._known.get(key)
        if known and known[0] > now:
            return known[1]
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{API_BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 401:
            return None
        r.raise_for_status()
        user = r.json()["id"]
        access = AccessToken(token=token, client_id=user, subject=user, scopes=["agent"])
        self._known = {k: v for k, v in self._known.items() if v[0] > now}
        self._known[key] = (now + self.KEEP_SECONDS, access)
        return access


class BnomeAuth(RemoteAuthProvider):
    """The protected-resource metadata (RFC 9728) at both addresses clients look: the path form the 401
    names (/.well-known/oauth-protected-resource/mcp) and the root form some clients try first."""

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = super().get_routes(mcp_path)
        return routes + [Route("/.well-known/oauth-protected-resource", endpoint=r.endpoint, methods=r.methods)
                         for r in routes if r.path.startswith("/.well-known/oauth-protected-resource/")]


mcp = FastMCP(
    name="Bnome",
    auth=BnomeAuth(
        token_verifier=BnomeTokens(),
        authorization_servers=[AnyHttpUrl(SITE_BASE)],
        base_url=f"{MCP_URL.scheme}://{MCP_URL.netloc}",
        resource_name="Bnome",
        resource_documentation=AnyHttpUrl(f"{SITE_BASE}/docs"),
    ),
    instructions=(
        "Bnome builds and runs software: apps and the systems around them, each with its own databases, "
        "durable queues, scheduled jobs and files. create_app and import_app start Bnome's build agent on a new "
        "app, modify_app changes one, and get_build_status shows how a build is going. list_systems and "
        "describe_system give a system's whole map: its programs and their APIs, services, databases, topics, "
        "jobs, files and connected services. The other tools read a system's data and logs, queue messages for "
        "its programs, manage its jobs, files and settings, and hand code changes to Bnome's own agent "
        "(ask_bnome_agent, agent_status). Building and running use the account's Bnome credits (get_credits)."
    ),
)


def _auth() -> dict:
    """Forward the caller's Bearer token from the incoming MCP request."""
    headers = get_http_headers(include_all=True)
    token = headers.get("authorization") or headers.get("Authorization")
    if not token:
        raise ValueError(
            "No Bnome token. The agent config must send Authorization: Bearer <token>. "
            "Run the Bnome connect installer to set it up."
        )
    return {"Authorization": token if token.lower().startswith("bearer ") else f"Bearer {token}"}


async def _req(method: str, path: str, *, json=None, auth=True, timeout=30.0):
    headers = _auth() if auth else {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.request(method, f"{API_BASE}{path}", json=json, headers=headers)
    if r.status_code >= 400:
        raise ValueError(f"Bnome API {r.status_code} on {method} {path}: {r.text[:300]}")
    if r.headers.get("content-type", "").startswith("application/json"):
        return r.json()
    return r.text


async def _raw(method: str, path: str, *, content: bytes, timeout: float = 60.0):
    """A request whose body is the bytes themselves — how Bnome's Files door takes a file."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.request(method, f"{API_BASE}{path}", content=content,
                                 headers={**_auth(), "Content-Type": "application/octet-stream"})
    if r.status_code >= 400:
        raise ValueError(f"Bnome API {r.status_code} on {method} {path}: {r.text[:300]}")
    return r.json()


def _abs(url: str | None) -> str | None:
    """API responses carry site-relative media paths; agents need full URLs."""
    if not url:
        return None
    return url if url.startswith("http") else f"{SITE_BASE}{url}"


# ---------------------------------------------------------------- apps

@mcp.tool(title="Create an app", annotations={"title": "Create an app", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def create_app(prompt: str, name: str | None = None) -> dict:
    """Create a brand-new Bnome app from a natural-language prompt.

    Spins up a workspace and starts an asynchronous build. Returns immediately with
    workspace_id + app_id and status='building'. get_build_status(app_id) reports the
    build: 'running' once the app is live at its live_url, or 'error'.

    Args:
        prompt: What to build, e.g. "a habit tracker with streaks and a dark theme".
        name:   Optional short workspace/app name. Defaults to the start of the prompt.
    """
    ws_name = (name or prompt).strip()[:60] or "New app"
    ws = await _req("POST", "/workspaces/", json={"name": ws_name, "description": prompt[:200]})
    ws_id = ws["id"]

    # The chat endpoint is the single chat-first entry point: with no existing app it
    # creates one and kicks off the background build (preview_app_with_agent).
    await _req("POST", f"/workspaces/{ws_id}/chat", json={"content": prompt, "role": "user"})

    # The app DB row is created at the very start of the build, so a short poll resolves it.
    app_id, status = None, "building"
    for _ in range(15):
        app = await _req("GET", f"/workspaces/{ws_id}/app")
        if app:
            app_id = app.get("id")
            status = app.get("status", "building")
            break
        await asyncio.sleep(1)

    return {
        "workspace_id": ws_id,
        "app_id": app_id,
        "status": status,
        "note": "Build runs in the background. Poll get_build_status(app_id) until 'running' or 'error'.",
    }


@mcp.tool(title="Import an app from GitHub", annotations={"title": "Import an app from GitHub", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
async def import_app(
    source_url: str,
    ref: str | None = None,
    subdir: str | None = None,
    name: str | None = None,
    instructions: str | None = None,
) -> dict:
    """Import an existing app from a public GitHub repository and put it live on Bnome.

    Bnome's build agent ports it to the Bnome stack (Vite + React frontend, FastAPI +
    SQLite backend, AI calls through the Bnome gateway so no API keys are needed),
    keeping its screens, features and look, and writes IMPORT_NOTES.md in the app with
    what changed. It runs in the background like create_app, and
    get_build_status(app_id) reports it ('running' or 'error'); porting takes 10-30 minutes.
    Counts as one app against the plan's app limit. Repos up to 100 MB as a zip.

    Args:
        source_url: https://github.com/owner/repo (public).
        ref: Branch, tag or commit. Defaults to the repository's default branch.
        subdir: Folder inside the repo that holds the app, for monorepos.
        name: App name. Defaults to one generated from the repository.
        instructions: What the port should do differently, e.g. "keep the landing page only".
    """
    body = {"source": source_url, "ref": ref, "subdir": subdir, "name": name, "instructions": instructions}
    started = await _req("POST", "/imports", json={k: v for k, v in body.items() if v}, timeout=180.0)
    started["note"] = ("Porting runs in the background. Poll get_build_status(app_id) until 'running' "
                       "or 'error'; the app's IMPORT_NOTES.md lists what changed.")
    return started


@mcp.tool(title="Check an app's build", annotations={"title": "Check an app's build", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def get_build_status(app_id: str) -> dict:
    """Check an app's current build/run status.

    Returns the app record including 'status' (building | running | preview | error |
    stopped) and 'live_url' once it is live: the state of a build create_app, import_app
    or modify_app started.
    """
    app = await _req("GET", f"/apps/{app_id}")
    return {
        "app_id": app.get("id"),
        "name": app.get("name"),
        "status": app.get("status"),
        "live_url": app.get("live_url"),
        "workspace_id": app.get("workspace_id") or app.get("project_id"),
        "screenshot_url": f"{API_BASE}/apps/{app.get('id')}/screenshot",
    }


@mcp.tool(title="List my apps", annotations={"title": "List my apps", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def list_my_apps() -> list:
    """List all apps owned by the authenticated Bnome user (id, name, status, live_url)."""
    apps = await _req("GET", "/apps/my")
    return [
        {
            "app_id": a.get("id"),
            "name": a.get("name"),
            "status": a.get("status"),
            "live_url": a.get("live_url"),
        }
        for a in apps
    ]


@mcp.tool(title="Change an app", annotations={"title": "Change an app", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False})
async def modify_app(workspace_id: str, prompt: str) -> dict:
    """Modify an existing running app with a natural-language change request.

    Sends the request into the app's workspace chat, which triggers the modification
    agent. The app must be in 'running' status. Returns immediately with status='building';
    get_build_status(app_id) reports when it is 'running' again.

    Args:
        workspace_id: The workspace that owns the app (from create_app / list context).
        prompt:       The change, e.g. "make the header sticky and add a settings page".
    """
    await _req("POST", f"/workspaces/{workspace_id}/chat", json={"content": prompt, "role": "user"})
    app = await _req("GET", f"/workspaces/{workspace_id}/app")
    return {
        "workspace_id": workspace_id,
        "app_id": app.get("id") if app else None,
        "status": "building",
        "note": "Modification is applying in the background. Poll get_build_status(app_id).",
    }


@mcp.tool(title="Set an app's address", annotations={"title": "Set an app's address", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False})
async def set_slug(app_id: str, slug: str) -> dict:
    """Set a human-readable vanity subdomain for an app -> https://<slug>.bnome.app/.

    Pass an empty string to reset back to the default UUID domain. The slug must be
    2-32 chars of a-z / 0-9 / hyphen (not start/end with a hyphen) and not reserved.

    Args:
        app_id: The app id (from create_app / list_my_apps).
        slug:   Desired subdomain, e.g. "voxels".
    """
    return await _req("POST", f"/apps/{app_id}/slug", json={"slug": slug})


@mcp.tool(title="Show the credit balance", annotations={"title": "Show the credit balance", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def get_credits() -> dict:
    """The user's Bnome credit balance: remaining, included, purchased, used and plan tier."""
    return await _req("GET", "/studio/credits")


# ---------------------------------------------------------------- systems: the platform's own runtime
#
# Everything below works on a *system* — a space of the user's with programs that run by themselves,
# their databases, queues, schedules, files and connected services. The builder tools above are
# "Bnome builds it for you"; these are "use what Bnome runs". The caller's own token, their own
# systems, their own credits.


@mcp.tool(title="List systems", annotations={"title": "List systems", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def list_systems() -> dict:
    """List the user's systems (spaces): each one's id, name and the programs it runs.

    A system is a live thing on Bnome: one or more programs with their own addresses, databases,
    queues, scheduled jobs, files and connected services. describe_system gives one of them whole.
    """
    return await _req("GET", "/agent/systems")


@mcp.tool(title="Describe a system", annotations={"title": "Describe a system", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def describe_system(system: str) -> dict:
    """Everything one system has, in one read — the map to work from.

    Gives, for the system: each program (slug, address, status, health, its own API read from its
    live contract, its scheduled jobs, its workers, the names of its settings), the services it
    declared (Postgres, Redis, anything from a public image), every database it keeps with tables
    and row counts, its topics (who publishes, who handles, what is waiting or failed), the links
    between its programs, its Files, and the outside services it is connected to or waiting on.

    Args:
        system: System id from list_systems.
    """
    return await _req("GET", f"/agent/systems/{system}", timeout=90.0)


async def _program_id(system: str, program: str) -> str:
    """A program by slug, name or id — the routes that act on one take its id."""
    data = await _req("GET", f"/agent/systems/{system}/programs")
    want = (program or "").strip().lower()
    for p in data["programs"]:
        if want in (p["program"].lower(), (p["slug"] or "").lower(), (p["name"] or "").lower()):
            return p["program"]
    have = ", ".join(p["slug"] for p in data["programs"]) or "none"
    raise ValueError(f"No program '{program}' in this system. Its programs: {have}.")


@mcp.tool(title="Read a table", annotations={"title": "Read a table", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def read_table(
    system: str,
    store: str,
    table: str,
    limit: int = 50,
    offset: int = 0,
    search: str = "",
    sort: str = "",
    newest_first: bool = False,
) -> dict:
    """Read rows from any table a system keeps — a program's own database, or a database service.

    Args:
        system: System id.
        store: Store id from describe_system (data[].id).
        table: Table name from describe_system (data[].tables[].name).
        limit: Rows to return, up to 200.
        offset: Skip this many rows.
        search: Keep only rows containing this text.
        sort: Column to order by.
        newest_first: Order descending.
    """
    q = f"?store={quote(store)}&table={quote(table)}&limit={max(1, min(limit, 200))}&offset={max(0, offset)}"
    if search:
        q += f"&q={quote(search)}"
    if sort:
        q += f"&sort={quote(sort)}&desc={'true' if newest_first else 'false'}"
    return await _req("GET", f"/system-data/{system}/rows{q}")


@mcp.tool(title="Query a system's data (read-only SQL)", annotations={"title": "Query a system's data (read-only SQL)", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def query_data(system: str, store: str, sql: str, limit: int = 200) -> dict:
    """Ask a system's data a question in SQL. Read-only: one SELECT, nothing is changed.

    SQLite runs it as the file's owner with only reading allowed; Postgres in a read-only
    transaction with a time limit. Column names are in describe_system (data[].tables[].columns).

    Args:
        system: System id.
        store: Store id from describe_system (data[].id). SQLite and Postgres only.
        sql: One SELECT.
        limit: Rows to return, up to 200.
    """
    return await _req("POST", f"/agent/systems/{system}/query", json={"store": store, "sql": sql, "limit": limit})


@mcp.tool(title="Queue a message for a system's programs", annotations={"title": "Queue a message for a system's programs", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False})
async def publish_event(
    system: str,
    topic: str,
    from_program: str,
    data: dict | list | str | int | float | bool | None = None,
    key: str | None = None,
) -> dict:
    """Put a message on one of a system's topics — the platform's durable queue.

    The platform keeps the message, brings it to every program that handles the topic, and tries
    again (after 10 s, 30 s, 2 min, 10 min, 30 min, 2 h, 6 h) until it is handled, so nothing is
    lost to a restart. This is how work gets queued between programs: a message put here reaches a
    program exactly as one from its sibling would. The topics a system has, and who handles them, are
    in describe_system.

    Args:
        system: System id.
        topic: A short lowercase name like booking.created or invoices.make.
        from_program: Which program the message is recorded as coming from (slug, name or id) —
            it is kept and shown exactly as that program's own code sending it.
        data: The message body, usually an object with the ids the handler needs.
        key: The same key sent twice stays one message, which makes a retry safe.
    """
    body = {"topic": topic, "data": data, "from_program": from_program, "key": key}
    return await _req("POST", f"/agent/systems/{system}/events", json=body)


@mcp.tool(title="List a system's queued messages", annotations={"title": "List a system's queued messages", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def list_events(system: str, topic: str = "", limit: int = 30) -> dict:
    """What a system put on its topics lately, and how each delivery went (done, waiting, failed, retries).

    Args:
        system: System id.
        topic: Only this topic. Omit for all.
        limit: How many, up to 100.
    """
    q = f"?limit={max(1, min(limit, 100))}" + (f"&topic={quote(topic)}" if topic else "")
    return await _req("GET", f"/agent/systems/{system}/events{q}")


@mcp.tool(title="Schedule a job", annotations={"title": "Schedule a job", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def schedule_job(
    system: str,
    program: str,
    name: str,
    path: str = "/api/job",
    every_minutes: int | None = None,
    daily_at: str | None = None,
    timezone: str = "UTC",
    description: str | None = None,
) -> dict:
    """Have the platform call one of a program's own routes on a clock — a scheduled job.

    The job belongs to the program and is called with the program's own token, so the route can be
    the program's and nobody else's. The platform calls it with POST, either every_minutes or at
    daily_at. Its name is what the owner reads on their canvas.

    Args:
        system: System id.
        program: Which program (slug, name or id).
        name: What this does, as the owner reads it, e.g. "Send tomorrow's reminders".
        path: The program's own route the platform calls, e.g. /api/jobs/reminders.
        every_minutes: Every N minutes (at least what the platform allows).
        daily_at: Once a day at HH:MM.
        timezone: The timezone daily_at is read in, e.g. Europe/Moscow.
        description: A longer note for the owner.
    """
    app_id = await _program_id(system, program)
    body = {"app_id": app_id, "name": name, "path": path, "timezone": timezone,
            "every_minutes": every_minutes, "daily_at": daily_at, "description": description}
    return await _req("POST", "/jobs", json={k: v for k, v in body.items() if v is not None})


@mcp.tool(title="Run a job now", annotations={"title": "Run a job now", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False})
async def run_job(job_id: str) -> dict:
    """Run one of a program's scheduled jobs right now, exactly as the schedule would call it.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job) or schedule_job.
    """
    return await _req("POST", f"/jobs/{job_id}/run", timeout=120.0)


@mcp.tool(title="Show a job's runs", annotations={"title": "Show a job's runs", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def job_runs(job_id: str, limit: int = 20) -> dict:
    """The last runs of a scheduled job: when each ran, how long it took, and what it answered.

    It shows whether work that should happen on a clock did.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job).
        limit: How many runs, newest first, up to 100.
    """
    return await _req("GET", f"/jobs/{job_id}/runs?limit={max(1, min(limit, 100))}")


@mcp.tool(title="Change or pause a job", annotations={"title": "Change or pause a job", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False})
async def set_job(job_id: str, enabled: bool | None = None, every_minutes: int | None = None,
                  daily_at: str | None = None, path: str | None = None, name: str | None = None) -> dict:
    """Change or switch off a scheduled job.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job).
        enabled: False stops it running without deleting it.
        every_minutes: New interval.
        daily_at: New time of day, HH:MM.
        path: The program's route it calls.
        name: What it does, as the owner reads it.
    """
    body = {"enabled": enabled, "every_minutes": every_minutes, "daily_at": daily_at, "path": path, "name": name}
    return await _req("PATCH", f"/jobs/{job_id}", json={k: v for k, v in body.items() if v is not None})


@mcp.tool(title="List a system's files", annotations={"title": "List a system's files", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def list_files(system: str, folder: str = "", search: str = "", trash: bool = False) -> dict:
    """A system's Files: one folder, or everything matching a search, with the room left on the plan.

    Every program of the system reads the same file at /files/<path>, so this is how files are
    shared. Each item's url downloads it.

    Args:
        system: System id.
        folder: Folder path, e.g. "Invoices/2026-10". Omit for the top.
        search: Find files by name across every folder.
        trash: Show the trash instead (files stay there 30 days).
    """
    q = f"?trash={'true' if trash else 'false'}"
    if folder:
        q += f"&folder={quote(folder)}"
    if search:
        q += f"&q={quote(search)}"
    got = await _req("GET", f"/workspaces/{system}/files{q}")
    for item in got.get("items") or []:
        item["url"] = _abs(item.get("url"))
    return got


@mcp.tool(title="Save a file to a system", annotations={"title": "Save a file to a system", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
async def save_file(system: str, name: str, folder: str = "", text: str | None = None,
                    from_url: str | None = None) -> dict:
    """Put a file into a system's Files, where its programs read it at /files/<folder>/<name>.

    Give either text (for anything textual — a price list, a CSV, a prompt, a note) or from_url
    (any publicly reachable file, which is fetched and stored). It counts toward the owner's plan.

    Args:
        system: System id.
        name: The file's name, with its extension.
        folder: Which folder to put it in; it is made if it does not exist.
        text: The file's contents, as text.
        from_url: Fetch the file from here instead.
    """
    if (text is None) == (from_url is None):
        raise ValueError("Give either text or from_url, not both.")
    if from_url:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            r = await client.get(from_url)
        if r.status_code >= 400:
            raise ValueError(f"{from_url} answered {r.status_code}.")
        body = r.content
    else:
        body = text.encode()
    q = f"?name={quote(name)}" + (f"&folder={quote(folder)}" if folder else "")
    saved = await _raw("POST", f"/workspaces/{system}/files{q}", content=body, timeout=180.0)
    saved["url"] = _abs(saved.get("url"))
    return saved


@mcp.tool(title="Delete a job", annotations={"title": "Delete a job", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False})
async def delete_job(job_id: str) -> dict:
    """Remove a scheduled job. set_job(enabled=False) stops a job without removing it.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job).
    """
    return await _req("DELETE", f"/jobs/{job_id}")


@mcp.tool(title="Move a file to the trash", annotations={"title": "Move a file to the trash", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False})
async def delete_file(system: str, file: str) -> dict:
    """Put a file of a system's Files in the trash, where it stays 30 days and the owner can restore it.

    It also comes off the owner's board. Only the owner empties the trash.

    Args:
        system: System id.
        file: The file's id from list_files.
    """
    return await _req("DELETE", f"/workspaces/{system}/files/{file}")


@mcp.tool(title="Read a program's logs", annotations={"title": "Read a program's logs", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def program_logs(system: str, program: str, file: str = "", lines: int = 80) -> dict:
    """The last lines a program wrote — its backend, its last frontend build, each of its workers.

    A program's servers write to log files beside their code, not to the container's output; these
    are those files.

    Args:
        system: System id.
        program: Which program (slug, name or id).
        file: One log by name, e.g. backend.log or worker.log. Omit for all of them.
        lines: How many of the last lines, up to 500.
    """
    q = f"?program={quote(program)}&lines={max(1, min(lines, 500))}" + (f"&file={quote(file)}" if file else "")
    return await _req("GET", f"/agent/systems/{system}/logs{q}", timeout=60.0)


@mcp.tool(title="Set a program setting", annotations={"title": "Set a program setting", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False})
async def set_setting(system: str, program: str, key: str, value: str, secret: bool = True) -> dict:
    """Put a setting or a key into a program's environment, where its code reads it as os.environ[KEY].

    A secret's value never comes back out — it can be replaced but not read. The program reads its
    environment once, when it starts, so a change needs a restart to take effect (ask_bnome_agent
    can do that, or the owner's Restart button).

    Outside services are reached through the system's connectors, which keep their own keys; this is
    for a program's own configuration.

    Args:
        system: System id.
        program: Which program (slug, name or id).
        key: CAPITALS, digits and underscores, e.g. STUDIO_TIMEZONE.
        value: What it is set to.
        secret: True for keys and passwords, False for a timezone or a feed URL the owner may read.
    """
    app_id = await _program_id(system, program)
    return await _req("POST", "/program-env", json={"app_id": app_id, "key": key, "value": value,
                                                     "is_secret": secret})


@mcp.tool(title="Ask Bnome's agent to change a system", annotations={"title": "Ask Bnome's agent to change a system", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False})
async def ask_bnome_agent(system: str, message: str) -> dict:
    """Send a request to Bnome's own agent — the one that writes and ships this system's code — to build or change something.

    That agent has the whole system mounted and the platform's hands: it writes the code, adds
    programs and services, and checks and publishes the system. It works in the background for
    minutes; agent_status(system) shows how far it is and what it answered. Each request is an edit
    of the owner's plan and spends their credits.

    Args:
        system: System id.
        message: What should be true when it is done.
    """
    sent = await _req("POST", f"/workspaces/{system}/chat", json={"content": message, "role": "user"},
                      timeout=120.0)
    return {"sent": sent.get("content"), "at": sent.get("created_at"),
            "note": "Bnome's agent is working on it. Poll agent_status(system) — it can take minutes."}


@mcp.tool(title="Check on Bnome's agent", annotations={"title": "Check on Bnome's agent", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def agent_status(system: str, limit: int = 6) -> dict:
    """What Bnome's own agent is doing in a system, and what it last said.

    Args:
        system: System id.
        limit: How many of the latest messages to return.
    """
    messages = await _req("GET", f"/workspaces/{system}/chat")
    latest = messages[-max(1, min(limit, 30)):]
    return {"working": bool(latest) and latest[-1].get("role") == "user",
            "messages": [{"role": m.get("role"), "content": (m.get("content") or "")[:4000],
                          "at": m.get("created_at")} for m in latest]}

if __name__ == "__main__":
    mcp.run(transport="http", host=HOST, port=PORT, path=MCP_URL.path)
