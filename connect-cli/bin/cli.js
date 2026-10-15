#!/usr/bin/env node
// @bnome/connect — wire the Bnome MCP server into your AI agent.
//
//   npx @bnome/connect install --claude          (browser sign-in: Google or password)
//   npx @bnome/connect install --cursor
//   npx @bnome/connect install --codex
//   npx @bnome/connect install --windsurf
//   npx @bnome/connect install --all
//   npx @bnome/connect install --claude --password   (headless: type email+password)
//
// Default flow opens bnome.com in your browser, where you're already logged in (any
// method), you click Approve, and a long-lived agent token is written into each
// selected agent's config. --password is a fallback for CI / headless machines.
import { login, mintAgentToken } from "../src/api.js";
import { browserAuth } from "../src/browserAuth.js";
import { ask, askHidden } from "../src/prompt.js";
import { ADAPTERS } from "../src/agents.js";

function parseArgs(argv) {
  const args = argv.slice(2);
  const cmd = args[0];
  const flags = new Set(args.slice(1).filter((a) => a.startsWith("--")).map((a) => a.slice(2)));
  return { cmd, flags };
}

function pickAgents(flags) {
  if (flags.has("all")) return Object.keys(ADAPTERS);
  return Object.keys(ADAPTERS).filter((k) => flags.has(k));
}

function help() {
  console.log(`bnome-connect — connect Bnome to your AI agent

Usage:
  npx @bnome/connect install --claude       Wire into Claude (~/.claude.json)
  npx @bnome/connect install --cursor       Wire into Cursor (~/.cursor/mcp.json)
  npx @bnome/connect install --codex        Wire into Codex (~/.codex/config.toml)
  npx @bnome/connect install --windsurf     Wire into Windsurf (~/.codeium/windsurf/mcp_config.json)
  npx @bnome/connect install --all          Wire into every supported agent

Options:
  --password    Sign in by typing email+password (headless), instead of the browser.

After installing, restart your agent. You'll have Bnome tools: create_app,
get_build_status, list_my_apps, modify_app.`);
}

// Returns a minted agent-token result: { token, mcp_url, expires_days }.
async function getAgentToken(agents, usePassword) {
  const label = agents.map((a) => ADAPTERS[a].label).join(" & ");
  if (usePassword) {
    const email = process.env.BNOME_EMAIL || (await ask("Bnome email: "));
    const password = process.env.BNOME_PASSWORD || (await askHidden("Bnome password: "));
    console.log("\nLogging in…");
    const access = await login(email, password);
    console.log("Minting agent token…");
    return await mintAgentToken(access);
  }
  // Browser flow: the /connect page mints the token itself and hands it back.
  const token = await browserAuth({ agent: label });
  return { token, mcp_url: "https://mcp.bnome.com/mcp", expires_days: 365 };
}

async function main() {
  const { cmd, flags } = parseArgs(process.argv);

  if (cmd !== "install" || flags.has("help") || flags.has("h")) {
    help();
    process.exit(cmd === "install" ? 0 : 1);
  }

  const agents = pickAgents(flags);
  if (agents.length === 0) {
    console.error("Pick at least one agent: --claude, --codex, or --all.\n");
    help();
    process.exit(1);
  }

  console.log("Connecting Bnome to: " + agents.map((a) => ADAPTERS[a].label).join(", ") + "\n");

  let mint;
  try {
    mint = await getAgentToken(agents, flags.has("password"));
  } catch (e) {
    console.error("✗ " + e.message);
    process.exit(1);
  }

  const { token, mcp_url: mcpUrl, expires_days } = mint;
  console.log(`\nGot a ${expires_days}-day agent token. Writing config…\n`);

  const results = [];
  for (const key of agents) {
    try {
      const file = ADAPTERS[key].install({ mcpUrl, token });
      results.push({ key, ok: true });
      console.log(`  ✓ ${ADAPTERS[key].label}: ${file}`);
    } catch (e) {
      results.push({ key, ok: false });
      console.log(`  ✗ ${ADAPTERS[key].label}: ${e.message}`);
    }
  }

  const ok = results.filter((r) => r.ok);
  if (ok.length) {
    console.log(`\nDone. Restart ${ok.map((r) => ADAPTERS[r.key].label).join(" & ")} to load the Bnome tools.`);
  }
  process.exit(ok.length ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
