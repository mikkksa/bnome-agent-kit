# The MCP server

`mcp_server.py` is what runs at `https://mcp.bnome.com/mcp`. It is a
[FastMCP](https://github.com/jlowin/fastmcp) server that holds **no business logic**:
every tool forwards the caller's `Authorization: Bearer` header to `bnome.com/api` and
reshapes the answer. That is the whole design, and it is why this file is readable.

You do not need to run it. `npx @bnome/connect install --claude` points your agent at
the hosted one, or add `https://mcp.bnome.com/mcp` to any client that supports MCP sign-in:
the server answers an unsigned request with 401 and its protected-resource metadata, which
names bnome.com as the authorization server (OAuth 2.1, PKCE, dynamic client registration). This is here so you can read exactly what your agent is doing, change
it, or run your own.

## Run your own

```bash
pip install -r requirements.txt
export BNOME_API_BASE=https://bnome.com/api     # the default
export BNOME_MCP_URL=http://127.0.0.1:8010/mcp   # required: the address clients reach it at
export BNOME_MCP_PORT=8010
python mcp_server.py
```

Then point your agent at it:

```bash
claude mcp add bnome http://127.0.0.1:8010/mcp --transport http \
  --header "Authorization: Bearer <your agent token>"
```

Get a token from [bnome.com/connect](https://bnome.com/connect), or with
`POST /api/auth/agent-token` using a normal session.

`client_test.py <token>` lists the tools over the wire, which is the quickest check that
a change took.

`deploy/` has the systemd unit and the nginx server block the hosted one uses —
streamable HTTP, so `proxy_buffering off` and a long read timeout matter.

## The API behind it

Two groups of routes, both taking the caller's own account token:

- **the builder** — `/api/workspaces`, `/api/apps`, `/api/imports`, and the credit
  balance, which have been there since the start;
- **the runtime** — `/api/agent/*`, the owner-facing twin of the two doors a system's
  own programs and agent use from inside. It serves the map of a system, a read-only SQL
  query over anything it keeps, its topics, and its programs' log files. Jobs
  (`/api/jobs`), settings (`/api/program-env`), Files
  (`/api/workspaces/{id}/files`), the chat and credits are the account's existing
  routes, used as they are.

Every route is scoped to a space the caller owns. Another account gets a 404, not a 403:
it is not told the system exists.

## Adding a tool

A tool is a decorated async function whose docstring is the whole interface — it is what
the model reads to decide whether to call it. Say what it does, when to use it, and when
not to. Then restart the server and check `client_test.py`.

Keep the server thin. If a tool needs logic, the logic belongs in the API.
