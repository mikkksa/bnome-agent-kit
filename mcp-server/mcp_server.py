"""
Bnome MCP server — thin wrapper over the existing Bnome REST API.

Design: this process holds NO business logic. Every tool forwards the caller's
Bearer token (read from the incoming MCP request headers) to https://bnome.com/api
and returns the JSON, reshaped into one "creation" record per result so agents see
the same fields for images, video, music, transcripts, clips and apps.

Async work mirrors the submit/poll pattern: generate_* / transcribe / create_app
start a background job. Pass wait_seconds to let the tool wait for a quick result,
otherwise poll get_job (studios) or get_build_status (apps).

Run:  python mcp_server.py            (http transport, port 8010, path /mcp)
Auth: the agent config supplies  Authorization: Bearer <bnome_jwt>  in headers.
"""
import os
import asyncio
import time
from typing import Literal
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

API_BASE = os.environ.get("BNOME_API_BASE", "https://bnome.com/api").rstrip("/")
SITE_BASE = API_BASE.rsplit("/api", 1)[0]
HOST = os.environ.get("BNOME_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("BNOME_MCP_PORT", "8010"))

MAX_WAIT_SECONDS = 120
STUDIO_KINDS = ("image", "video", "music")
STUDIO_PAGES = {"image": "images", "video": "video", "music": "music"}

mcp = FastMCP(
    name="Bnome",
    instructions=(
        "Bnome is infrastructure a business runs on, and any agent can work on it. Two ways in. "
        "(1) Bnome builds it for you: create_app / import_app / modify_app start Bnome's own build agent. "
        "(2) You build on Bnome: list_systems then describe_system gives a system's whole map — its programs "
        "and their live APIs, the services it declared, every database it keeps, its topics (durable queues "
        "with retries), its scheduled jobs, its Files and its connected services. From there read its data "
        "(read_table, query_data), hand its programs work (publish_event), put work on a clock "
        "(schedule_job, run_job, job_runs), share files (list_files, save_file, delete_file), set a program's settings "
        "(set_setting), look at what broke (program_logs, list_events), and have Bnome's own agent write and "
        "ship the code (ask_bnome_agent, agent_status). "
        "Bnome builds live web apps and makes images, video, music, transcripts and clips. "
        "Apps: create_app starts a background build; poll get_build_status until 'running' or 'error'. "
        "import_app does the same for an existing app from a public GitHub repo: the build agent ports it. "
        "Studios: generate_image / generate_video / generate_music / transcribe / make_clips start async jobs. "
        "Films: make_film plans and draws a storyboard, shoot_film turns it into a short film. try_on dresses a "
        "person photo in clothing items. "
        "Pass wait_seconds (up to 120) for a quick result, otherwise poll get_job with the returned id and kind. "
        "Every run spends the user's Bnome credits: check list_models for prices and say the cost before "
        "expensive runs (video). Results are private unless the user asks to share them (public=true or "
        "set_visibility). Show finished media to the user with its url."
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


def _from_generation(g: dict) -> dict:
    kind = g["modality"]
    return {
        "id": g["id"],
        "kind": kind,
        "status": g["status"],
        "prompt": g["prompt"],
        "model": g["alias"],
        "url": _abs(g.get("url")),
        "cover_url": _abs(g.get("cover")),
        "cover_pending": g.get("cover_pending", False),
        "credits": g.get("credits"),
        "is_public": g.get("is_public"),
        "error": g.get("error"),
        "created_at": g.get("created_at"),
        "web_url": f"{SITE_BASE}/{STUDIO_PAGES[kind]}",
    }


def _from_transcript(t: dict) -> dict:
    record = {
        "id": t["id"],
        "kind": "transcript",
        "status": t["status"],
        "title": t.get("filename"),
        "language": t.get("language"),
        "duration_sec": t.get("duration_sec"),
        "credits": t.get("credits"),
        "documents_ready": t.get("derived") or [],
        "error": t.get("error"),
        "created_at": t.get("created_at"),
        "web_url": f"{SITE_BASE}/transcribe",
    }
    if "segments" in t:
        record["text"] = t.get("text")
        record["segments"] = [
            {"speaker": s.get("speaker"), "start_ms": s.get("start"), "text": s.get("text")}
            for s in t.get("segments") or []
        ]
        record["documents"] = t.get("documents") or {}
    return record


def _from_clips(c: dict) -> dict:
    return {
        "id": c["id"],
        "kind": "clips",
        "status": c["status"],
        "stage": c.get("stage"),
        "title": c.get("filename"),
        "credits": c.get("credits"),
        "error": c.get("error"),
        "created_at": c.get("created_at"),
        "clips": [
            {
                "title": clip.get("title"),
                "hook": clip.get("hook"),
                "status": clip.get("status"),
                "url": _abs(clip.get("url")),
                "thumb_url": _abs(clip.get("thumb")),
                "start": clip.get("start"),
                "end": clip.get("end"),
                "score": clip.get("score"),
            }
            for clip in c.get("clips") or []
        ],
        "web_url": f"{SITE_BASE}/clips",
    }


def _is_settled(record: dict) -> bool:
    if record["status"] == "failed":
        return True
    if record["status"] != "done":
        return False
    # A song is "done" before its cover art lands.
    return not record.get("cover_pending")


async def _fetch_job(kind: str, job_id: str) -> dict:
    # Reading an item is also what moves its upstream job forward on the backend.
    if kind in STUDIO_KINDS:
        return _from_generation(await _req("GET", f"/studio/generations/{job_id}"))
    if kind == "transcript":
        return _from_transcript(await _req("GET", f"/transcribe/{job_id}"))
    if kind == "clips":
        return _from_clips(await _req("GET", f"/clips/{job_id}"))
    raise ValueError(f"Unknown kind '{kind}'. Use image, video, music, transcript or clips.")


async def _wait(kind: str, record: dict, wait_seconds: int) -> dict:
    deadline = time.monotonic() + max(0, min(wait_seconds, MAX_WAIT_SECONDS))
    interval = {"image": 3, "video": 6, "music": 5, "transcript": 5, "clips": 5}[kind]
    while not _is_settled(record) and time.monotonic() + interval <= deadline:
        await asyncio.sleep(interval)
        record = await _fetch_job(kind, record["id"])
    if not _is_settled(record):
        record["note"] = f"Still {record['status']}. Poll get_job(id='{record['id']}', kind='{kind}')."
    return record


async def _generate(alias: str, prompt: str, params: dict, public: bool, wait_seconds: int) -> dict:
    gen = await _req(
        "POST", "/studio/generate",
        json={"alias": alias, "prompt": prompt, "params": params, "public": public},
        timeout=120.0,
    )
    record = _from_generation(gen)
    return await _wait(record["kind"], record, wait_seconds)


# ---------------------------------------------------------------- apps

@mcp.tool
async def create_app(prompt: str, name: str | None = None) -> dict:
    """Create a brand-new Bnome app from a natural-language prompt.

    Spins up a workspace and starts an asynchronous build. Returns immediately with
    workspace_id + app_id and status='building'. Poll get_build_status(app_id) until
    it becomes 'running' (the app is live at its live_url) or 'error'.

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


@mcp.tool
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
    what changed. Starts in the background like create_app: poll
    get_build_status(app_id) until 'running' or 'error' (porting can take 10-30 minutes).
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


@mcp.tool
async def get_build_status(app_id: str) -> dict:
    """Check an app's current build/run status.

    Returns the app record including 'status' (building | running | preview | error |
    stopped) and 'live_url' once it is live. Poll this after create_app or modify_app.
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


@mcp.tool
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


@mcp.tool
async def modify_app(workspace_id: str, prompt: str) -> dict:
    """Modify an existing running app with a natural-language change request.

    Sends the request into the app's workspace chat, which triggers the modification
    agent. The app must be in 'running' status. Returns immediately with status='building';
    poll get_build_status(app_id) until it is 'running' again.

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


@mcp.tool
async def set_slug(app_id: str, slug: str) -> dict:
    """Set a human-readable vanity subdomain for an app -> https://<slug>.bnome.app/.

    Pass an empty string to reset back to the default UUID domain. The slug must be
    2-32 chars of a-z / 0-9 / hyphen (not start/end with a hyphen) and not reserved.

    Args:
        app_id: The app id (from create_app / list_my_apps).
        slug:   Desired subdomain, e.g. "voxels".
    """
    return await _req("POST", f"/apps/{app_id}/slug", json={"slug": slug})


# ---------------------------------------------------------------- studios

@mcp.tool
async def list_models(kind: Literal["image", "video", "music"] | None = None) -> list:
    """List Bnome's studio models with their price in credits and when to use each.

    Args:
        kind: Only models of this kind. Omit for all.
    """
    data = await _req("GET", "/studio/models", auth=False)
    return [
        {
            "model": m["alias"],
            "label": m["label"],
            "kind": m["modality"],
            "tier": m.get("tier"),
            "default": m.get("default", False),
            "credits": m.get("cost"),
            "when_to_use": m.get("when_to_use"),
        }
        for m in data["models"]
        if kind is None or m["modality"] == kind
    ]


@mcp.tool
async def get_credits() -> dict:
    """The user's Bnome credit balance: remaining, included, purchased, used and plan tier."""
    return await _req("GET", "/studio/credits")


@mcp.tool
async def generate_image(
    prompt: str,
    model: str = "bnome/image",
    aspect_ratio: Literal["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"] | None = None,
    reference_images: list[str] | None = None,
    public: bool = False,
    wait_seconds: int = 60,
) -> dict:
    """Generate an image in Bnome's image studio. Spends credits (see list_models).

    Args:
        prompt: What to draw — subject, style, light, composition.
        model: Model alias from list_models(kind="image"). Default GPT Image 2.
        aspect_ratio: Frame shape. Not every model takes it (Seedream sizes itself).
        reference_images: Public image URLs to edit or combine (bnome/image-nano only).
        public: Also show it in Bnome's public Explore gallery.
        wait_seconds: Wait up to this long (max 120) for the finished image.
    """
    params = {}
    if aspect_ratio:
        params["aspect_ratio"] = aspect_ratio
    if reference_images:
        params["image_input"] = reference_images
    return await _generate(model, prompt, params, public, wait_seconds)


@mcp.tool
async def generate_video(
    prompt: str,
    model: str = "bnome/video",
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9",
    duration_sec: Literal[4, 8, 12] = 8,
    public: bool = False,
    wait_seconds: int = 0,
) -> dict:
    """Generate a video clip in Bnome's video studio. Paid plans only; spends credits.

    Video takes one to three minutes: keep wait_seconds at 0 and poll get_job.

    Args:
        prompt: The scene — subject, action, camera movement, style.
        model: Model alias from list_models(kind="video"). Default Seedance 1.5 Pro.
        aspect_ratio: Frame shape.
        duration_sec: Clip length in seconds.
        public: Also show it in Bnome's public Explore gallery.
        wait_seconds: Wait up to this long (max 120) for the finished clip.
    """
    params = {"aspect_ratio": aspect_ratio, "duration": str(duration_sec)}
    return await _generate(model, prompt, params, public, wait_seconds)


@mcp.tool
async def generate_music(
    prompt: str,
    instrumental: bool = False,
    title: str | None = None,
    style: str | None = None,
    public: bool = False,
    wait_seconds: int = 0,
) -> dict:
    """Make a song in Bnome's music studio (Suno), with generated cover art. Spends credits.

    With only a prompt, Suno writes the lyrics. Give title and style for full control;
    the prompt is then sung as literal lyrics (unless instrumental).

    Args:
        prompt: What the song is about, or its lyrics when title/style are set.
        instrumental: No vocals.
        title: Song title (turns on custom mode).
        style: Genre, mood, instruments, tempo (turns on custom mode).
        public: Also show it in Bnome's public Explore gallery.
        wait_seconds: Wait up to this long (max 120) for the finished song.
    """
    params = {"instrumental": instrumental}
    if title or style:
        params.update({"custom_mode": True, "title": title or "", "style": style or ""})
    return await _generate("bnome/music", prompt, params, public, wait_seconds)


@mcp.tool
async def transcribe(audio_url: str, wait_seconds: int = 0) -> dict:
    """Transcribe audio or video by public URL, with speakers and language detection.

    Spends 0.42 credits per started minute once it finishes. Poll get_job(kind="transcript").

    Args:
        audio_url: A publicly reachable audio or video file URL.
        wait_seconds: Wait up to this long (max 120) for the finished transcript.
    """
    started = await _req("POST", "/transcribe/start", json={"audio_url": audio_url}, timeout=120.0)
    return await _wait("transcript", _from_transcript(started), wait_seconds)


@mcp.tool
async def make_clips(video_url: str, count: int = 5, reframe: bool = True) -> dict:
    """Cut a long video into short vertical clips (15-75 seconds each) around its best moments.

    Bnome transcribes the video, picks self-contained moments and renders the clips,
    reframed to 9:16 around the speaker. Spends 0.6 credits per minute of source when
    it finishes. Runs in the background: poll get_job(id, kind="clips"). Clips are private.

    Args:
        video_url: A direct, publicly reachable video file URL (up to 2 GB).
        count: How many clips to cut, 1-8.
        reframe: Crop to vertical 9:16 following the speaker. False keeps the original frame.
    """
    started = await _req(
        "POST", "/clips/start",
        json={"video_url": video_url, "count": count, "reframe": reframe}, timeout=60.0,
    )
    return _from_clips(started)


def _film(film: dict) -> dict:
    """A film with absolute URLs, so agents can show frames, poster and film."""
    for key in ("poster_url", "film_url", "cover_url"):
        film[key] = _abs(film.get(key))
    for group in ("characters", "frames", "shots"):
        for item in film.get(group) or []:
            item["url"] = _abs(item.get("url"))
    film["web_url"] = f"{SITE_BASE}/film"
    return film


@mcp.tool
async def make_film(
    idea: str,
    aspect_ratio: Literal["16:9", "9:16"] = "16:9",
    length: Literal["short", "medium", "long"] = "medium",
    music: bool = True,
    frame_model: Literal["bnome/image-nano", "bnome/image", "bnome/image-flux", "bnome/image-seedream"] = "bnome/image-nano",
    shot_model: Literal["bnome/video", "bnome/video-kling", "bnome/video-kling-pro", "bnome/video-veo"] = "bnome/video",
) -> dict:
    """Make a short film from an idea, with characters and a look that stay consistent.

    Bnome writes the plan, draws character sheets and key frames (the storyboard), and
    after shoot_film animates each shot from one key frame to the next and joins them
    under a score. Step 1: returns the film at once (status 'writing'). Poll get_film
    until 'storyboard', show the frames to the user, change any with redraw_frame, then
    call shoot_film. Short = 3 shots (~24 s), medium = 5 (~40 s), long = 7 (~56 s).
    When the story changes place the film cuts, so a take never has to travel between places.
    With the default models roughly 60-160 credits in total; needs a paid plan.

    Args:
        idea: The film in a sentence or a paragraph, in any language.
        aspect_ratio: 16:9 for screens, 9:16 for phones.
        length: short, medium or long.
        music: Lay an instrumental score under the film.
        frame_model: What draws the character sheets, key frames and poster: Nano Banana 2 (default),
            GPT Image 2, Flux 2 Pro or Seedream 4.
        shot_model: What animates each shot: Seedance 1.5 Pro (default, ~15 credits a shot),
            Kling 3.0 (~59, the smoothest moves), Kling 3.0 Pro (~113.4, 1080p, the most real-looking;
            keeps its own sound instead of a score) or Veo 3.1 (~210, premium). Can be changed at shoot_film.
    """
    body = {"idea": idea, "aspect_ratio": aspect_ratio, "length": length, "music": music,
            "frame_model": frame_model, "shot_model": shot_model}
    return _film(await _req("POST", "/films", json=body, timeout=120.0))


@mcp.tool
async def get_film(id: str) -> dict:
    """A film's progress: plan, characters, key frames, shots, poster and the finished film.

    Status goes writing -> drawing -> storyboard -> (shoot_film) -> shooting -> assembling -> done.
    Reading a film is also what moves it forward, so poll it every 10-20 seconds.
    """
    return _film(await _req("GET", f"/films/{id}", timeout=120.0))


@mcp.tool
async def redraw_frame(
    id: str,
    index: int,
    description: str | None = None,
    model: Literal["bnome/image-nano", "bnome/image", "bnome/image-flux", "bnome/image-seedream"] | None = None,
) -> dict:
    """Redraw one key frame of a film before it is shot, optionally with a new description or model.

    Args:
        id: Film id.
        index: The frame's index (0-based) from get_film.
        description: What the frame should show instead. Omit to redraw the same idea.
        model: Draw this frame with another image model. Omit to use the film's frame model.
    """
    return _film(await _req("POST", f"/films/{id}/frames/{index}", json={"description": description, "model": model},
                            timeout=120.0))


@mcp.tool
async def shoot_film(id: str, model: Literal["bnome/video", "bnome/video-kling", "bnome/video-kling-pro", "bnome/video-veo"] | None = None) -> dict:
    """Step 2: shoot a film whose storyboard is ready. Each shot moves from its first key frame
    to its last; the score and poster are made alongside and ffmpeg joins it all. Takes a
    few minutes: poll get_film until 'done', then share film_url and poster_url.

    Args:
        id: Film id.
        model: Shoot with another video model: Seedance 1.5 Pro (~15 credits a shot), Kling 3.0
            (~59, the smoothest moves), Kling 3.0 Pro (~113.4, 1080p with its own sound) or Veo 3.1
            (~210). Omit to use the film's shot model.
    """
    return _film(await _req("POST", f"/films/{id}/shoot", json={"model": model}, timeout=120.0))


@mcp.tool
async def try_on(person_image_url: str, item_urls: list[str], notes: str | None = None, wait_seconds: int = 60) -> dict:
    """Virtual try-on: a photo of a person and 1-3 clothing items become one realistic photo
    of that person wearing them. Items can be image links or product page links (their
    og:image is used). Use only photos of the user or of people who agreed. Private; about
    2 credits.

    Args:
        person_image_url: A clear photo of the person, ideally full-length and front-facing.
        item_urls: 1-3 garment image links or product page links.
        notes: Styling notes, e.g. "tuck the shirt in".
        wait_seconds: Wait up to this long (max 120) for the finished photo.
    """
    started = await _req("POST", "/try-on", json={"person_url": person_image_url, "item_urls": item_urls,
                                                   "notes": notes or ""}, timeout=120.0)
    return await _wait("image", _from_generation(started), wait_seconds)


@mcp.tool
async def derive_document(
    id: str,
    kind: Literal["summary", "article", "social", "meeting_notes"],
) -> dict:
    """Turn a finished transcript into a summary, an article, social posts or meeting notes.

    Args:
        id: Transcript id.
        kind: What to write from it.
    """
    return await _req("POST", f"/transcribe/{id}/derive", json={"kind": kind}, timeout=120.0)


@mcp.tool
async def get_job(
    id: str,
    kind: Literal["image", "video", "music", "transcript", "clips"],
    wait_seconds: int = 0,
) -> dict:
    """Check a studio job and get its result once done (media url, transcript or clips).

    Args:
        id: The id returned when the job started.
        kind: image, video, music, transcript or clips.
        wait_seconds: Wait up to this long (max 120) for it to finish.
    """
    return await _wait(kind, await _fetch_job(kind, id), wait_seconds)


@mcp.tool
async def list_creations(
    kind: Literal["image", "video", "music", "transcript", "clips", "app"],
    limit: int = 24,
) -> list:
    """List the user's own creations of one kind, newest first.

    Args:
        kind: image, video, music, transcript, clips or app.
        limit: How many to return (1-100).
    """
    limit = max(1, min(limit, 100))
    if kind in STUDIO_KINDS:
        items = await _req("GET", "/studio/generations?limit=200")
        return [_from_generation(g) for g in items if g["modality"] == kind][:limit]
    if kind == "transcript":
        data = await _req("GET", "/transcribe/list")
        return [_from_transcript(t) for t in data["items"]][:limit]
    if kind == "clips":
        data = await _req("GET", "/clips/list")
        return [_from_clips(c) for c in data["items"]][:limit]
    workspaces = await _req("GET", "/workspaces/my")
    return [
        {
            "id": ws["application"]["id"],
            "kind": "app",
            "name": ws["application"].get("name") or ws.get("name"),
            "status": ws["application"].get("status"),
            "live_url": ws["application"].get("live_url"),
            "workspace_id": ws["id"],
            "screenshot_url": f"{API_BASE}/apps/{ws['application']['id']}/screenshot",
            "created_at": ws.get("created_at"),
        }
        for ws in workspaces
        if ws.get("application")
    ][:limit]


@mcp.tool
async def set_visibility(id: str, public: bool) -> dict:
    """Show or hide an image, video or song in Bnome's public Explore gallery.

    Args:
        id: The creation id.
        public: True to share publicly, False to keep it private.
    """
    return _from_generation(await _req("POST", f"/studio/generations/{id}/publish", json={"public": public}))


@mcp.tool
async def delete_creation(
    id: str,
    kind: Literal["image", "video", "music", "clips"],
    confirm: bool,
) -> dict:
    """Permanently delete an image, video, song or clips set. Ask the user first.

    Args:
        id: The creation id.
        kind: image, video, music or clips.
        confirm: Must be true; only pass it after the user agreed to delete.
    """
    if not confirm:
        raise ValueError("Deletion needs confirm=true after the user agreed.")
    if kind == "clips":
        return await _req("DELETE", f"/clips/{id}")
    return await _req("DELETE", f"/studio/generations/{id}")


# ---------------------------------------------------------------- systems: the platform's own runtime
#
# Everything below works on a *system* — a space of the user's with programs that run by themselves,
# their databases, queues, schedules, files and connected services. The builder tools above are
# "Bnome builds it for you"; these are "use what Bnome runs". The caller's own token, their own
# systems, their own credits.


@mcp.tool
async def list_systems() -> dict:
    """List the user's systems (spaces): each one's id, name and the programs it runs.

    A system is a live thing on Bnome: one or more programs with their own addresses, databases,
    queues, scheduled jobs, files and connected services. Start here, then describe_system.
    """
    return await _req("GET", "/agent/systems")


@mcp.tool
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


@mcp.tool
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


@mcp.tool
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


@mcp.tool
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
    lost to a restart. This is how work gets queued between programs; use it to hand a program work
    the same way its sibling would. The topics a system has, and who handles them, are in
    describe_system.

    Args:
        system: System id.
        topic: A short lowercase name like booking.created or invoices.make.
        from_program: Which program the message is recorded as coming from (slug, name or id) —
            it is kept and shown exactly as that program's own code sending it.
        data: The message body, usually an object with the ids the handler needs.
        key: Send the same key twice and it stays one message. Use it to make a retry safe.
    """
    body = {"topic": topic, "data": data, "from_program": from_program, "key": key}
    return await _req("POST", f"/agent/systems/{system}/events", json=body)


@mcp.tool
async def list_events(system: str, topic: str = "", limit: int = 30) -> dict:
    """What a system put on its topics lately, and how each delivery went (done, waiting, failed, retries).

    Args:
        system: System id.
        topic: Only this topic. Omit for all.
        limit: How many, up to 100.
    """
    q = f"?limit={max(1, min(limit, 100))}" + (f"&topic={quote(topic)}" if topic else "")
    return await _req("GET", f"/agent/systems/{system}/events{q}")


@mcp.tool
async def schedule_job(
    system: str,
    program: str,
    name: str,
    path: str = "/api/job",
    every_minutes: int | None = None,
    daily_at: str | None = None,
    timezone: str = "UTC",
    method: Literal["POST", "GET", "PUT", "PATCH", "DELETE"] = "POST",
    description: str | None = None,
) -> dict:
    """Have the platform call one of a program's own routes on a clock — a scheduled job.

    The job belongs to the program and is called with the program's own token, so the route can be
    the program's and nobody else's. Say either every_minutes or daily_at. Name it in the owner's
    words: they read it on their canvas.

    Args:
        system: System id.
        program: Which program (slug, name or id).
        name: What this does, in the owner's words, e.g. "Send tomorrow's reminders".
        path: The program's own route the platform calls, e.g. /api/jobs/reminders.
        every_minutes: Every N minutes (at least what the platform allows).
        daily_at: Once a day at HH:MM.
        timezone: The timezone daily_at is read in, e.g. Europe/Moscow.
        method: HTTP method for the call.
        description: A longer note for the owner.
    """
    app_id = await _program_id(system, program)
    body = {"app_id": app_id, "name": name, "path": path, "method": method, "timezone": timezone,
            "every_minutes": every_minutes, "daily_at": daily_at, "description": description}
    return await _req("POST", "/jobs", json={k: v for k, v in body.items() if v is not None})


@mcp.tool
async def run_job(job_id: str) -> dict:
    """Run one of a program's scheduled jobs right now, exactly as the schedule would call it.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job) or schedule_job.
    """
    return await _req("POST", f"/jobs/{job_id}/run", timeout=120.0)


@mcp.tool
async def job_runs(job_id: str, limit: int = 20) -> dict:
    """The last runs of a scheduled job: when each ran, how long it took, and what it answered.

    Where to look when work that should happen on a clock did not.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job).
        limit: How many runs, newest first, up to 100.
    """
    return await _req("GET", f"/jobs/{job_id}/runs?limit={max(1, min(limit, 100))}")


@mcp.tool
async def set_job(job_id: str, enabled: bool | None = None, every_minutes: int | None = None,
                  daily_at: str | None = None, path: str | None = None, name: str | None = None) -> dict:
    """Change or switch off a scheduled job.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job).
        enabled: False stops it running without deleting it.
        every_minutes: New interval.
        daily_at: New time of day, HH:MM.
        path: The program's route it calls.
        name: What it does, in the owner's words.
    """
    body = {"enabled": enabled, "every_minutes": every_minutes, "daily_at": daily_at, "path": path, "name": name}
    return await _req("PATCH", f"/jobs/{job_id}", json={k: v for k, v in body.items() if v is not None})


@mcp.tool
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


@mcp.tool
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


@mcp.tool
async def delete_job(job_id: str) -> dict:
    """Remove a scheduled job. Use set_job(enabled=False) instead to keep it but stop it running.

    Args:
        job_id: The job's id, from describe_system (programs[].jobs[].job).
    """
    return await _req("DELETE", f"/jobs/{job_id}")


@mcp.tool
async def delete_file(system: str, file: str) -> dict:
    """Put a file of a system's Files in the trash, where it stays 30 days and the owner can restore it.

    It also comes off the owner's board. Only the owner empties the trash.

    Args:
        system: System id.
        file: The file's id from list_files.
    """
    return await _req("DELETE", f"/workspaces/{system}/files/{file}")


@mcp.tool
async def program_logs(system: str, program: str, file: str = "", lines: int = 80) -> dict:
    """The last lines a program wrote — its backend, its last frontend build, each of its workers.

    Where to look first when something is wrong: a program's servers write to log files beside
    their code, not to the container's output.

    Args:
        system: System id.
        program: Which program (slug, name or id).
        file: One log by name, e.g. backend.log or worker.log. Omit for all of them.
        lines: How many of the last lines, up to 500.
    """
    q = f"?program={quote(program)}&lines={max(1, min(lines, 500))}" + (f"&file={quote(file)}" if file else "")
    return await _req("GET", f"/agent/systems/{system}/logs{q}", timeout=60.0)


@mcp.tool
async def set_setting(system: str, program: str, key: str, value: str, secret: bool = True) -> dict:
    """Put a setting or a key into a program's environment, where its code reads it as os.environ[KEY].

    A secret's value never comes back out — it can be replaced but not read. The program reads its
    environment once, when it starts, so a change needs a restart to take effect (ask_bnome_agent
    can do that, or the owner's Restart button).

    An API key for an outside service does NOT belong here: a system reaches outside services
    through its connectors, so the key stays with the connector and every program can use it.

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


@mcp.tool
async def ask_bnome_agent(system: str, message: str) -> dict:
    """Ask Bnome's own agent — the one that writes and ships this system's code — to build or change something.

    Use this for anything that needs the system's code written, a new program, a service started, or
    the system checked and published: that agent has the whole system mounted and the platform's
    hands. Say the outcome and the limits, not the steps. It works in the background for minutes;
    agent_status(system) shows how far it is and what it answered.

    Every message is an edit of the owner's plan and spends their credits, so send one clear
    request, not a stream of them. Write it in the owner's language.

    Args:
        system: System id.
        message: What should be true when it is done.
    """
    sent = await _req("POST", f"/workspaces/{system}/chat", json={"content": message, "role": "user"},
                      timeout=120.0)
    return {"sent": sent.get("content"), "at": sent.get("created_at"),
            "note": "Bnome's agent is working on it. Poll agent_status(system) — it can take minutes."}


@mcp.tool
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
    mcp.run(transport="http", host=HOST, port=PORT)
