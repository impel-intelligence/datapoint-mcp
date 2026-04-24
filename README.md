# Datapoint MCP

An MCP server that gives Claude Code tools for creating and managing human evaluation surveys via [Datapoint AI](https://trydatapoint.com).

## Tools

| Tool | Description |
|------|-------------|
| `setup` | Authenticate with your Datapoint AI account (opens browser) |
| `upload_media` | Upload local images, audio, or video so they can be used in a survey |
| `plan_survey` | Design a survey from a natural language description |
| `create_survey` | Launch a survey from a plan |
| `check_survey` | Check status, progress, and aggregated results |
| `get_survey_responses` | Get the raw per-annotator responses (paginated) |
| `list_surveys` | List all your surveys |
| `check_balance` | Check your account balance |
| `add_credits` | Open a checkout link to top up your account |

## Install in Claude Code

### As a plugin (recommended)

```
/plugin marketplace add impel-intelligence/datapoint-mcp
/plugin install datapoint@datapoint
```

To pick up new versions, run `/plugin marketplace update datapoint` then `/plugin update datapoint@datapoint`. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

### As a raw MCP server

If you'd rather wire it in directly, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "datapoint": {
      "command": "uvx",
      "args": ["--refresh", "--from", "git+https://github.com/impel-intelligence/datapoint-mcp.git", "datapoint-mcp"]
    }
  }
}
```

## Usage

Once installed, ask Claude to create a survey:

> "Survey 20 people: which logo do they prefer, A or B?"

Claude will use `plan_survey` to design it, show you the plan and cost, then `create_survey` to launch it. Use `check_survey` to monitor progress and see results.

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
