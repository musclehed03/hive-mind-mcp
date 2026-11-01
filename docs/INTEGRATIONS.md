# Integrations — connect Hive-Mind in minutes (Block 12)

Hive-Mind is one MCP server with two transports and one
OpenAI-compatible model client. There is nothing to install
beyond this repo and Python 3.12: no SDK, no framework, no
account. Pick the transport your client speaks, point the model
client at an endpoint, and verify with the one-line checks below.

The 8 `hivemind_` tools are the same on every transport. The
lock-in spec (`docs/HIVE-MIND-LOCK-IN-SPEC.md`) is the source of
truth for tool names and shapes; nothing here adds a tool.

## Transports

### Stdio (default — most MCP clients)

The server reads one JSON object per line on stdin and writes one
response per line on stdout. Run it from the repo folder:

```bash
python -m app.mcp_server
```

Verify it answers (prints the 8 tools and exits):

```bash
python -m app.mcp_server --list-tools
```

### SSE over HTTP (clients that need a URL)

For browser-based clients, remote editors, and front ends that
cannot spawn a process. Localhost only by default:

```bash
python -m app.sse_server
# Hive-Mind MCP SSE at http://127.0.0.1:8765/sse (localhost only)
```

Verify the health reply:

```bash
curl http://127.0.0.1:8765/
```

The SSE shape: `GET /sse` opens a stream and sends an `endpoint`
event naming `/messages?session_id=<id>`; `POST /messages` takes
one JSON-RPC request and returns 202, with the response arriving
on the stream as a `message` event. See `app/sse_server.py` for
the exact protocol. A live check of SSE inside a real MCP client
is still outstanding (Sonja-side) — the server itself is covered
by tests over localhost.

## MCP client configs (copy, paste, fix the one path)

In every snippet below, replace `ABSOLUTE_PATH_TO_HIVE_MIND_MCP`
with the absolute path of this repo folder on your machine, e.g.
`/home/sonja-on-fire/hive-mind-mcp` on Sonja's Linux machine.
No key appears in any snippet: keys live in `.env` only (see
`.env.example`), never in client config files.

### Claude Code (terminal)

Run once, from the repo folder:

```bash
claude mcp add hive-mind -- python -m app.mcp_server
```

Check it is listed:

```bash
claude mcp list
```

### Codex (terminal)

Codex reads MCP servers from `~/.codex/config.toml`. Add this
block, replacing `ABSOLUTE_PATH_TO_HIVE_MIND_MCP` with the
absolute path of this repo folder, then restart Codex:

```toml
[mcp_servers.hive-mind]
command = "python"
args = ["-m", "app.mcp_server"]
cwd = "ABSOLUTE_PATH_TO_HIVE_MIND_MCP"
```

### Claude Desktop

Add to `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/`; Windows:
`%APPDATA%\Claude\`), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "hive-mind": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "ABSOLUTE_PATH_TO_HIVE_MIND_MCP"
    }
  }
}
```

### VS Code (stdio)

Create `.vscode/mcp.json` in the repo folder (or any workspace
folder — the `cwd` below is what matters):

```json
{
  "servers": {
    "hive-mind": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "ABSOLUTE_PATH_TO_HIVE_MIND_MCP"
    }
  }
}
```

### VS Code (SSE)

If you prefer the HTTP transport, start `python -m app.sse_server`
first, then use:

```json
{
  "servers": {
    "hive-mind-sse": {
      "type": "http",
      "url": "http://127.0.0.1:8765/sse"
    }
  }
}
```

### Any other MCP client

Any client that speaks MCP over stdio works with the stdio
command above; any client that speaks MCP over SSE works with
the `/sse` URL above. If a client offers neither, it cannot use
Hive-Mind yet — that is a client gap, not a Hive-Mind gap.

## Model endpoints (one code path, any OpenAI-compatible root)

`app/live_meta.py` posts to `{base_url}/chat/completions`. The
base URL and model come from the environment, so Ollama, OpenRouter,
OpenWebUI, and the Meta Model API all use the same code, the same
scrubber-before-send rule, and the same 5-call-per-process budget.
The defaults are the Meta Model API. Only the key changes hands:
whatever remote endpoint you point at, its API key goes in the
`META_API_KEY` environment variable (the name is historical — when
the base URL is overridden, the value is sent only to that
endpoint, never to Meta). Loopback endpoints need no key at all
(see Ollama below). Fake clients stay the default: nothing
here makes a live call unless `HIVE_MIND_LIVE=1` is set in the
shell for that run.

### Ollama (local, no cloud)

Ollama serves its OpenAI-compatible API on port 11434 by default.
In the shell that runs a live gate:

```bash
export HIVE_MIND_LIVE=1
export HIVE_MIND_META_BASE_URL=http://localhost:11434/v1
export HIVE_MIND_META_MODEL=gemma3:4b
```

No `META_API_KEY` is needed for a loopback base URL (Block 15):
with no key set, the client sends no `Authorization` header to
`localhost` / `127.x.x.x` / `::1`, and a key is still sent if one
is configured. Remote endpoints refuse without a key.

Verify Ollama itself answers (no key needed for this check):

```bash
curl http://localhost:11434/v1/models
```

A live Ollama end-to-end check from this codebase is still
outstanding (Sonja-side — no Ollama exists in the build VM).
Local endpoints earn the same EXP as cloud endpoints; nothing
here nudges you toward spending cloud credits.

### OpenRouter

```bash
export HIVE_MIND_LIVE=1
export HIVE_MIND_META_BASE_URL=https://openrouter.ai/api/v1
export HIVE_MIND_META_MODEL=meta-llama/llama-3.1-8b-instruct
export META_API_KEY=your-openrouter-key-in-this-shell-only
```

Use the exact `provider/model` name from your OpenRouter account.
The key is set in the shell for one run only — never committed,
never pasted in chat.

### OpenWebUI

Point the base URL at your own OpenWebUI install's
OpenAI-compatible root. Check it in OpenWebUI under
Settings → Connections; it is commonly:

```bash
export HIVE_MIND_LIVE=1
export HIVE_MIND_META_BASE_URL=http://localhost:8080/api/v1
export HIVE_MIND_META_MODEL=the-model-name-shown-in-openwebui
```

If your install uses a different port or path, use that — the
rule is "the OpenAI-compatible root", not one fixed URL.

### Meta Model API (default)

```bash
export HIVE_MIND_LIVE=1
export HIVE_MIND_META_BASE_URL=https://api.meta.ai/v1
export HIVE_MIND_META_MODEL=muse-spark-1.3
export META_API_KEY=your-meta-key-in-this-shell-only
```

The $150 free credits / $100 spend-warning guard from the live
gates still applies: verify Billing before any live run, and
unset the variables when the run is done.

## Hotkeys (honest version)

Hive-Mind ships no global hotkey daemon, and this doc does not
pretend otherwise. Hotkeys live in the client or the operating
system, and the fastest path is to focus the client you already
use:

- **Windows:** pin your MCP client (or terminal) to the taskbar,
  then `Win+1` … `Win+9` focuses it by position.
- **macOS:** `Cmd+Tab` switches to the client; Spotlight
  (`Cmd+Space`, type the client name) launches it.
- **Linux (GNOME/KDE):** bind a custom shortcut in Settings →
  Keyboard to launch your terminal or client; `Super` + typing
  the app name also works.
- **VS Code:** `Ctrl+Shift+P` (or `Cmd+Shift+P`) opens the
  command palette, where the MCP commands live. A keybinding
  that toggles the terminal (so the CLI client is one key away)
  in `keybindings.json`:

```json
[
  {
    "key": "ctrl+alt+h",
    "command": "workbench.action.terminal.toggleTerminal"
  }
]
```

- **Claude Code / terminal clients:** there is no hotkey inside
  the tool — focus the terminal, and `claude` (or your client
  command) is one command away.

If a client adds its own Hive-Mind shortcut or palette command
later, it belongs in that client's docs, not here.

## What is verified, what is not

- Verified in this repo's tests (mocked HTTP, localhost only):
  the generalised base URL / model config, the SSE protocol
  (initialize, tools/list, tools/call over a real local stream),
  and the presence of every snippet section in this file.
- Still outstanding, Sonja-side only: a live Ollama endpoint
  check, an SSE check inside a real MCP client, and Day's
  achromatopsia re-check of the new growth-stage visuals.
  Nothing in this doc claims those are done.
