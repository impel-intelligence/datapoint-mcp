"""Entry point for running the Datapoint AI MCP server.

Usage:
    python -m mcp_server
"""

from mcp_server.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
