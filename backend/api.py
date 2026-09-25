"""API HTTP in sola lettura: serve al frontend i conti dei trader come JSON.

Legge il database (data/accounts.db) e non scrive mai: chi lo popola e' demo_seed.py
(operazioni inventate) oppure, in modalita' reale, il motore (COME_RENDERLO_REALE.txt).

Avvio in locale, dalla cartella del progetto:

    uv run python -m uvicorn backend.api:app --port 8000

Variabili d'ambiente (tutte facoltative):
  MODEL_LABEL      nome del modello mostrato in dashboard (default "Simulato"; in
                   modalita' reale mettici il nome del modello usato dagli agenti)
  ALLOWED_ORIGINS  origini ammesse dal CORS, separate da virgola. Serve solo se il
                   frontend e' su un dominio diverso dall'API (Render: sito statico
                   + web service). In locale il proxy di Vite rende inutile il CORS.
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import market
from backend.accounts import Account
from backend.database import read_log

# I tre trader della demo (le strategie stanno in reset.py).
names = ["Alpha", "Beta", "Gamma"]
lastnames = ["High Risk", "Medium Risk", "Low Risk"]
model_label = os.getenv("MODEL_LABEL", "").strip() or "Simulato"
short_model_names = [model_label] * len(names)

# Colore di ogni tipo di riga nel pannello di log della dashboard.
LOG_COLORS = {
    "trace": "#87CEEB",
    "agent": "#00dddd",
    "function": "#00dd00",
    "generation": "#dddd00",
    "response": "#aa00dd",
    "account": "#dd0000",
}
DEFAULT_LOG_COLOR = "#87CEEB"

roster = [
    {"name": name, "lastname": lastname, "model_name": model_name}
    for name, lastname, model_name in zip(names, lastnames, short_model_names)
]
roster_by_name = {trader["name"].lower(): trader for trader in roster}

app = FastAPI(title="Trading Floor")

_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_methods=["GET"],  # l'API e' in sola lettura, non serve altro
        allow_headers=["*"],
    )


def average_cost(account: Account, symbol: str) -> float:
    """Average price paid across this symbol's buys, for per-holding profit."""
    spend = sum(t.price * t.quantity for t in account.transactions if t.symbol == symbol and t.quantity > 0)
    bought = sum(t.quantity for t in account.transactions if t.symbol == symbol and t.quantity > 0)
    return spend / bought if bought else 0.0


def holdings_detail(account: Account) -> list[dict]:
    """Current holdings enriched with price, market value and unrealised profit."""
    details = []
    for symbol, quantity in account.holdings.items():
        price = market.get_share_price(symbol)
        cost = average_cost(account, symbol)
        details.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "avg_cost": cost,
                "market_value": price * quantity,
                "unrealized_pnl": (price - cost) * quantity,
            }
        )
    return details


def require_trader(name: str) -> dict:
    trader = roster_by_name.get(name.lower())
    if not trader:
        raise HTTPException(status_code=404, detail=f"Unknown trader {name}")
    return trader


@app.get("/api/traders")
def get_traders() -> list[dict]:
    """The traders on the floor."""
    return roster


@app.get("/api/market")
def get_market() -> dict:
    """Which price source is live, and whether the market is open."""
    source = "massive" if market.massive_api_key else "simulator"
    return {"source": source, "is_market_open": market.is_market_open()}


@app.get("/api/traders/{name}")
def get_trader(name: str) -> dict:
    """A trader's full state: value, profit, holdings, transactions and history."""
    trader = require_trader(name)
    account = Account.get(name)
    holdings = holdings_detail(account)
    portfolio_value = account.balance + sum(h["market_value"] for h in holdings)
    return {
        "name": trader["name"],
        "lastname": trader["lastname"],
        "model_name": trader["model_name"],
        "balance": account.balance,
        "strategy": account.strategy,
        "portfolio_value": portfolio_value,
        "pnl": account.calculate_profit_loss(portfolio_value),
        "holdings": holdings,
        "transactions": account.list_transactions(),
        "time_series": [{"datetime": ts, "value": value} for ts, value in account.portfolio_value_time_series],
    }


@app.get("/api/traders/{name}/logs")
def get_trader_logs(name: str, last_n: int = 13) -> list[dict]:
    """Recent trace and account log lines, oldest first, with their panel colour."""
    require_trader(name)
    rows = list(read_log(name, last_n))
    return [
        {"datetime": ts, "type": kind, "message": message, "color": LOG_COLORS.get(kind, DEFAULT_LOG_COLOR)}
        for ts, kind, message in rows
    ]
