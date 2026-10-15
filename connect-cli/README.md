# @bnome/connect

The installer. One command signs you in and wires the Bnome MCP server into your
agent's config.

```bash
npx @bnome/connect install --claude     # ~/.claude.json
npx @bnome/connect install --codex      # ~/.codex/config.toml
npx @bnome/connect install --cursor
npx @bnome/connect install --windsurf
npx @bnome/connect install --all
```

Your browser opens `bnome.com/connect`, you read what the token grants and press
**Approve**, and it is written into each selected agent's config. Restart the agent.

`--password` signs in with email and password instead of the browser, for headless and
CI machines.

## How the browser flow is safe

The CLI starts a one-shot server on `127.0.0.1`, opens `bnome.com/connect?cb=…`, and
Bnome redirects the minted token back to that loopback address. The page **refuses any
callback that is not loopback**, so a crafted `/connect?cb=evil.com` link cannot take a
signed-in user's token. The installer never sees your password in this flow.

## What the token is

A year-long signed pass that acts as you on Bnome: it can build and change your apps,
read the data your systems keep, hand their programs work, change their schedules and
settings, put files in and take them out, and spend your credits. Only your own account
is reachable.

Take it back with **Sign out AI agents** on your Bnome profile. That withdraws every
agent token the account ever handed out at once — your browser session is unaffected —
and running the installer again mints a new one.

## This source

Published as `@bnome/connect` on npm (MIT). `reference/ConnectPage.js` is the page on
bnome.com the CLI opens, included so the whole flow is readable in one place; it is not
part of the package.
