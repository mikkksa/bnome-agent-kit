// Browser connect flow: open bnome.com/connect in the user's browser (where they're
// already logged in via Google OR password), let them approve, and catch the minted
// agent token on a one-shot loopback server. No password ever touches the terminal.
import http from "node:http";
import crypto from "node:crypto";
import { spawn } from "node:child_process";

const WEB_BASE = process.env.BNOME_WEB_BASE || "https://bnome.com";

function openBrowser(url) {
  const platform = process.platform;
  const cmd = platform === "darwin" ? "open" : platform === "win32" ? "cmd" : "xdg-open";
  const args = platform === "win32" ? ["/c", "start", "", url] : [url];
  try {
    spawn(cmd, args, { detached: true, stdio: "ignore" }).unref();
    return true;
  } catch {
    return false;
  }
}

const DONE_HTML = (ok) => `<!doctype html><meta charset=utf-8>
<title>Bnome Connect</title>
<body style="font-family:Inter,system-ui,sans-serif;background:#09090b;color:#e4e4e7;display:flex;height:100vh;margin:0;align-items:center;justify-content:center;text-align:center">
<div><h2>${ok ? "Connected 🦔" : "Something went wrong"}</h2>
<p style="color:#a1a1aa">${ok ? "Return to your terminal — you can close this tab." : "Close this tab and try again."}</p></div>`;

export function browserAuth({ agent = "your AI agent", timeoutMs = 300000 } = {}) {
  return new Promise((resolve, reject) => {
    const state = crypto.randomBytes(16).toString("hex");

    const server = http.createServer((req, res) => {
      const url = new URL(req.url, `http://127.0.0.1`);
      if (url.pathname !== "/callback") {
        res.writeHead(404).end();
        return;
      }
      const token = url.searchParams.get("token");
      const gotState = url.searchParams.get("state");
      const ok = Boolean(token) && gotState === state;
      res.writeHead(200, { "Content-Type": "text/html" }).end(DONE_HTML(ok));
      clearTimeout(timer);
      server.close();
      if (ok) resolve(token);
      else reject(new Error(gotState !== state ? "state mismatch (possible CSRF) — aborted" : "no token in callback"));
    });

    const timer = setTimeout(() => {
      server.close();
      reject(new Error("Timed out waiting for browser approval (5 min)."));
    }, timeoutMs);

    // Bind to an ephemeral loopback port, then open the browser at the real port.
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      const cb = `http://127.0.0.1:${port}/callback`;
      const connectUrl =
        `${WEB_BASE}/connect?cb=${encodeURIComponent(cb)}&state=${state}&agent=${encodeURIComponent(agent)}`;
      console.log("Opening your browser to approve the connection…");
      console.log("If it doesn't open, paste this URL:\n  " + connectUrl + "\n");
      if (process.env.BNOME_NO_OPEN !== "1") openBrowser(connectUrl);
    });
  });
}
