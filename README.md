<!-- mcp-name: io.github.impel-intelligence/datapoint-mcp -->

# Datapoint MCP

> Get real human opinions from inside any MCP client. Run surveys, A/B preference comparisons, ratings, and rankings on text, images, audio, and video — without leaving your editor.

[![MCP](https://img.shields.io/badge/MCP-server-000000)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by Datapoint AI](https://img.shields.io/badge/powered%20by-Datapoint%20AI-7c3aed)](https://trydatapoint.com)

Datapoint MCP is an [MCP server](https://modelcontextprotocol.io) that gives Claude, GPT, Gemini, and any other MCP-capable agent the ability to recruit real humans for evaluation tasks, then return aggregated results back into the conversation. Built on top of [Datapoint AI](https://trydatapoint.com).

## Why

LLMs are great at generating options and bad at telling you which one a real person will prefer. Datapoint MCP closes that loop — your agent can hand off to a panel of real humans and pick up the results a few minutes later.

## Use cases

- **Design & UX** — A/B test logos, landing pages, screens, ad creative, copy
- **AI evaluation** — human ratings of model outputs, side-by-side comparisons, hallucination checks
- **Preference data** — collect RLHF / DPO pairs at scale
- **Dataset labeling** — classification, ranking, captioning, content moderation
- **Product research** — quick concept tests, naming, pricing reads
- **Human-in-the-loop checks** — gate an agent before it ships something irreversible

## Tools

| Tool | Description |
|------|-------------|
| `setup` | Authenticate with your Datapoint AI account (opens browser) |
| `upload_media` | Upload local images, audio, or video so they can be used in a survey |
| `plan_survey` | Design a survey from a natural language description |
| `create_survey` | Launch a survey from a plan |
| `check_survey` | Check status, progress, and aggregated results |
| `get_survey_responses` | Get raw per-annotator responses (paginated) |
| `list_surveys` | List all your surveys |
| `pause_survey` | Pause task serving for an active survey (in-flight responses keep arriving) |
| `resume_survey` | Resume task serving for a paused survey |
| `check_balance` | Check your account balance |
| `add_credits` | Open a checkout link to top up your account |

## Install

Requires [`uv`](https://docs.astral.sh/uv/getting-started/installation/) on your `PATH`.

### Claude Code

**As a plugin (recommended):**

```
/plugin marketplace add impel-intelligence/datapoint-mcp
/plugin install datapoint@datapoint
```

To pick up new versions: `/plugin marketplace update datapoint` then `/plugin update datapoint@datapoint`.

**As a raw MCP server** (in `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "datapoint": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/impel-intelligence/datapoint-mcp.git", "datapoint-mcp"]
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "datapoint": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/impel-intelligence/datapoint-mcp.git", "datapoint-mcp"]
    }
  }
}
```

Restart Claude Desktop, then ask it to run `setup`.

### Cursor

Add to `~/.cursor/mcp.json` (or via Settings → MCP):

```json
{
  "mcpServers": {
    "datapoint": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/impel-intelligence/datapoint-mcp.git", "datapoint-mcp"]
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "datapoint": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/impel-intelligence/datapoint-mcp.git", "datapoint-mcp"]
    }
  }
}
```

### VS Code (GitHub Copilot Chat / agent mode)

Add to your workspace `.vscode/mcp.json`:

```json
{
  "servers": {
    "datapoint": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/impel-intelligence/datapoint-mcp.git", "datapoint-mcp"]
    }
  }
}
```

### Any other MCP client

Run the binary over stdio:

```bash
uvx --from git+https://github.com/impel-intelligence/datapoint-mcp.git datapoint-mcp
```

## Usage

Once installed, just ask:

> "Survey 20 people: which logo do they prefer, A or B?"
>
> "Get human ratings on these three model outputs — which sounds most natural?"
>
> "Run a quick A/B test on these two landing-page headlines."

The agent calls `plan_survey` to design it, shows you the plan and cost, then calls `create_survey` to launch. Use `check_survey` to monitor progress and read aggregated results.

Run `setup` first to authenticate if you haven't already.

### Chain surveys (multi-step flow)

Some surveys have dependent questions — the second only makes sense given a specific answer to the first. Describe it that way and Claude will plan a **chain**:

> "Ask 20 listeners if they could understand the speaker in this clip. If yes, rate the audio quality 1–5. If not, skip the rating."

A chain ties 2–5 steps together into a single unit of annotator work: every step is served to the same annotator, in order, and a per-step `skip_if` rule can terminate the walk early. Claude will show you the full chain structure (steps, any skip conditions, cost) and wait for your confirmation before calling `create_survey`.

The cost shown in `plan_survey` is the upper bound (every walk completes every step); when `skip_if` rules fire, walks cost proportionally less.

## Configuration

| Environment variable | Description |
|---------------------|-------------|
| `DATAPOINT_API_KEY` | API key (overrides saved config) |
| `DATAPOINT_BASE_URL` | API base URL (default: `https://api.trydatapoint.com/data-labelling/v1`) |

## How it compares

| | Datapoint MCP | Mechanical Turk | Prolific | UserTesting |
|---|---|---|---|---|
| Run from inside an AI agent / IDE | ✅ | ❌ | ❌ | ❌ |
| Designed for AI/LLM evaluation | ✅ | ⚠️ | ⚠️ | ❌ |
| Pay-as-you-go via API | ✅ | ✅ | ✅ | ❌ |
| Supports media (image / audio / video) | ✅ | ✅ | ✅ | ✅ |
| Minutes to first response | ✅ | ⚠️ | ⚠️ | ❌ |

## Links

- Homepage: [trydatapoint.com](https://trydatapoint.com)
- MCP spec: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- Issues / discussions: [GitHub](https://github.com/impel-intelligence/datapoint-mcp/discussions)

## License

MIT — see [LICENSE](LICENSE).
