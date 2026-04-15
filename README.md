# Datapoint MCP

An MCP server that gives Claude Code tools for creating and managing human evaluation surveys via [Datapoint AI](https://trydatapoint.com).

## Tools

| Tool | Description |
|------|-------------|
| `setup` | Authenticate with your Datapoint AI account (opens browser) |
| `plan_survey` | Design a survey from a natural language description |
| `create_survey` | Launch a survey from a plan |
| `check_survey` | Check status, progress, and results |
| `list_surveys` | List all your surveys |
| `check_balance` | Check your account balance |

## Install in Claude Code

Add to your Claude Code settings (`~/.claude/settings.json`):

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

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

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
