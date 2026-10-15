// Per-agent config writers. Each adapter injects the Bnome MCP server block into
// that agent's config file, preserving everything else. To add another agent,
// add one adapter here.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function ensureDir(file) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
}

function backup(file) {
  if (fs.existsSync(file)) {
    fs.copyFileSync(file, `${file}.bak.bnome`);
  }
}

// Generic JSON writer for agents that store MCP servers under mcpServers.bnome.
// They differ only in the config file path and the URL field name (Windsurf uses
// `serverUrl`, Claude/Cursor use `url`) plus a couple of extra fields for Claude.
function installJsonAgent(file, { mcpUrl, token }, { urlKey = "url", extra = {} } = {}) {
  let cfg = {};
  if (fs.existsSync(file)) {
    try { cfg = JSON.parse(fs.readFileSync(file, "utf8") || "{}"); }
    catch { throw new Error(`${file} exists but is not valid JSON — fix or move it, then retry.`); }
  }
  cfg.mcpServers = cfg.mcpServers || {};
  cfg.mcpServers.bnome = {
    ...extra,
    [urlKey]: mcpUrl,
    headers: { Authorization: `Bearer ${token}` },
  };
  ensureDir(file);
  backup(file);
  fs.writeFileSync(file, JSON.stringify(cfg, null, 2) + "\n");
  return file;
}

// --- Claude: ~/.claude.json, JSON, key mcpServers.bnome ---
function installClaude(creds) {
  return installJsonAgent(
    path.join(os.homedir(), ".claude.json"),
    creds,
    { urlKey: "url", extra: { type: "http" } }
  );
}

// --- Cursor: ~/.cursor/mcp.json, JSON, key mcpServers.bnome (url + headers) ---
function installCursor(creds) {
  return installJsonAgent(
    path.join(os.homedir(), ".cursor", "mcp.json"),
    creds,
    { urlKey: "url" }
  );
}

// --- Windsurf: ~/.codeium/windsurf/mcp_config.json, JSON, serverUrl + headers ---
function installWindsurf(creds) {
  return installJsonAgent(
    path.join(os.homedir(), ".codeium", "windsurf", "mcp_config.json"),
    creds,
    { urlKey: "serverUrl" }
  );
}

// --- Codex: ~/.codex/config.toml, TOML, table [mcp_servers.bnome] ---
function installCodex({ mcpUrl, token }) {
  const file = path.join(os.homedir(), ".codex", "config.toml");
  let text = "";
  if (fs.existsSync(file)) text = fs.readFileSync(file, "utf8");

  // Drop any prior [mcp_servers.bnome] block (from the header line up to the next
  // table header or EOF) so re-running refreshes the token instead of duplicating.
  text = text.replace(/(^|\n)\[mcp_servers\.bnome\][\s\S]*?(?=\n\[|\s*$)/g, "$1").replace(/\n{3,}/g, "\n\n");

  const block =
    `[mcp_servers.bnome]\n` +
    `url = "${mcpUrl}"\n` +
    `http_headers = { Authorization = "Bearer ${token}" }\n`;

  const sep = text.length && !text.endsWith("\n") ? "\n\n" : text.endsWith("\n\n") || !text.length ? "" : "\n";
  const out = text + sep + block;
  ensureDir(file);
  backup(file);
  fs.writeFileSync(file, out);
  return file;
}

export const ADAPTERS = {
  claude: { label: "Claude", install: installClaude },
  cursor: { label: "Cursor", install: installCursor },
  codex: { label: "Codex", install: installCodex },
  windsurf: { label: "Windsurf", install: installWindsurf },
};
