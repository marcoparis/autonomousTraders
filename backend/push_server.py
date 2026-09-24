"""
Server MCP che espone il tool "push" agli agenti-trader.

Sostituisce Pushover con ntfy.sh. Il contratto del tool resta lo stesso, con
un campo opzionale in piu': il nome del trader, cosi' la notifica dice chi ha
operato senza doverlo dedurre dal testo.

Gira come sottoprocesso via stdio, lanciato da backend/mcp_servers.py:
    uv run -m backend.push_server
"""

from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from .notifications import is_enabled, notify_trader_push

mcp = FastMCP("push_server")


class PushModelArgs(BaseModel):
    message: str = Field(description="A brief message to push")
    trader: str | None = Field(
        default=None,
        description="Your name, so the notification says who is reporting",
    )


@mcp.tool()
def push(args: PushModelArgs) -> str:
    """Send a push notification with this brief message"""
    print(f"Push [{args.trader or 'unknown'}]: {args.message}", flush=True)

    if not is_enabled():
        # Senza NTFY_TOPIC il trading floor deve funzionare lo stesso:
        # l'agente riceve una risposta valida e prosegue.
        return "Push notification skipped: no NTFY_TOPIC configured"

    sent = notify_trader_push(args.message, args.trader)
    return "Push notification sent" if sent else "Push notification failed"


if __name__ == "__main__":
    mcp.run(transport="stdio")
