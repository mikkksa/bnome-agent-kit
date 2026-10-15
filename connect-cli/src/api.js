// Bnome API client — login + mint an agent token. Node 18+ (global fetch).
const API_BASE = process.env.BNOME_API_BASE || "https://bnome.com/api";

export async function login(email, password) {
  const r = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`Login failed (${r.status}): ${t.slice(0, 200)}`);
  }
  const data = await r.json();
  const token = data.access_token;
  if (!token) throw new Error("Login succeeded but no access_token in response.");
  return token;
}

export async function mintAgentToken(accessToken) {
  const r = await fetch(`${API_BASE}/auth/agent-token`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`Could not mint agent token (${r.status}): ${t.slice(0, 200)}`);
  }
  // { token, type, expires_days, mcp_url }
  return await r.json();
}
