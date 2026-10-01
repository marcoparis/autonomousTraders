"""Client MCP che legge conto e strategia di un trader dal server accounts_server.py."""

from pathlib import Path

import mcp
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

from .mcp_servers import SERVER_ENV

params = StdioServerParameters(
    command="uv",
    args=["run", "-m", "backend.accounts_server"],
    cwd=str(Path(__file__).resolve().parent.parent),
    env=SERVER_ENV or None,
)

async def read_accounts_resource(name):
    async with stdio_client(params) as streams, mcp.ClientSession(*streams) as session:
        await session.initialize()
        result = await session.read_resource(f"accounts://accounts_server/{name}")
        return result.contents[0].text

async def read_strategy_resource(name):
    async with stdio_client(params) as streams, mcp.ClientSession(*streams) as session:
        await session.initialize()
        result = await session.read_resource(f"accounts://strategy/{name}")
        return result.contents[0].text
