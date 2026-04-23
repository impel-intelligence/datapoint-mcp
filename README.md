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
/plugin install impel-intelligence/datapoint-mcp
```

You'll receive plugin updates automatically. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

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

## Configuration

| Environment variable | Description |
|---------------------|-------------|
| `DATAPOINT_API_KEY` | API key (overrides saved config) |
| `DATAPOINT_BASE_URL` | API base URL (default: `https://api.trydatapoint.com/data-labelling/v1`) |
