import os
from pathlib import Path
from dotenv import load_dotenv
from agents.mcp import MCPServerStdio, create_static_tool_filter
from .market import massive_api_key

load_dotenv(override=True)

PROJECT_DIR = str(Path(__file__).resolve().parent.parent)
tavily_env = {"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY")}
TIMEOUT = 120


def _passthrough_env(*names: str) -> dict[str, str]:
    """Variabili da girare a un server MCP. I sottoprocessi stdio ereditano solo
    un ambiente minimo (PATH, HOME...): senza questo, su GitHub Actions dove non
    c'e' un .env, i server non vedrebbero NTFY_TOPIC ne' ACCOUNTS_DB."""
    return {n: os.environ[n] for n in names if os.environ.get(n)}


# Il DB e le notifiche servono ai server che scrivono i conti e mandano le push
SERVER_ENV = _passthrough_env(
    "ACCOUNTS_DB", "NTFY_TOPIC", "NTFY_SERVER", "NTFY_TOKEN", "DASHBOARD_URL"
)

# The market data server for the trader.
# With a key, hand the agent Massive's own market data server, run locally over stdio.
# Without one, use our market server, which serves simulated prices.
if massive_api_key:
    market_params = {
        "command": "uvx",
        "args": [
            "--with", "mcp<2",
            "--from", "git+https://github.com/massive-com/mcp_massive@v0.10.0",
            "mcp_massive"
        ],
        "env": {"MASSIVE_API_KEY": massive_api_key},
    }
else:
    market_params = {
        "command": "uv",
        "args": ["run", "-m", "backend.market_server"],
        "cwd": PROJECT_DIR
    }

def trader_mcp_servers() -> list[MCPServerStdio]:
    """The trader's MCP servers: our Accounts server, Push Notification and Market data."""
    params = [
        {"command": "uv", "args": ["run", "-m", "backend.accounts_server"], "cwd": PROJECT_DIR, "env": SERVER_ENV},
        {"command": "uv", "args": ["run", "-m", "backend.push_server"], "cwd": PROJECT_DIR, "env": SERVER_ENV},
        market_params,
    ]
    return [MCPServerStdio(p, client_session_timeout_seconds=TIMEOUT) for p in params]


def researcher_mcp_servers(name: str) -> list[MCPServerStdio]:
    """The researcher's MCP servers: Fetch, Tavily web search and Memory.

    Tavily's server offers several tools; we restrict it to web search so the
    researcher reaches for plain search rather than its heavier crawl or deep-research tools.
    """
    fetch = MCPServerStdio(
        {"command": "uvx", "args": ["--with", "mcp<2","mcp-server-fetch"]},
        client_session_timeout_seconds=TIMEOUT,
    )
    search = MCPServerStdio(
        {"command": "npx", "args": ["-y", "tavily-mcp@latest"], "env": tavily_env},
        client_session_timeout_seconds=TIMEOUT,
        tool_filter=create_static_tool_filter(allowed_tool_names=["tavily_search"]),
    )
    memory = MCPServerStdio(
        {
            "command": "npx",
            "args": ["-y", "mcp-memory-libsql"],
            "env": {"LIBSQL_URL": f"file:./memory/{name}.db"},
        },
        client_session_timeout_seconds=TIMEOUT,
    )
    return [fetch, search, memory]
    
