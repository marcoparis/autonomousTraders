"""Genera uno storico di trading SIMULATO per la demo pubblica, senza chiamare nessun modello.

Non usa LLM ne' rete: le operazioni sono decise da regole semplici (una per profilo di
rischio) e i prezzi arrivano da backend/market_simulator.py, lo stesso che alimenta l'API
pubblicata. Lo storico e' quindi coerente con cio' che la dashboard mostra oggi.

Serve solo a popolare la vetrina. I dati sono inventati e vanno presentati come tali.

    ACCOUNTS_DB=data/accounts.db uv run -m backend.demo_seed
"""

import random
import sqlite3
from datetime import datetime, timedelta, timezone

from .accounts import Account, Transaction, SPREAD
from .database import DB
from .market_simulator import simulated_price
from .reset import reset_traders

DAYS = 10
SESSION_HOURS_UTC = (15, 20)  # come il cron del workflow

# Per ogni trader: universo di titoli, quota di cassa per acquisto, probabilita' di operare
PROFILES = {
    "Alpha": {
        "symbols": ["TSLA", "NVDA", "AMD", "PLTR", "SMCI", "SHOP"],
        "cash_share": (0.30, 0.55),
        "trade_prob": 0.75,
        "take_profit": 0.06,
        "stop_loss": -0.08,
        "buy_reasons": [
            "Momentum forte e catalizzatore di breve: entro con posizione ampia.",
            "Il titolo rompe il massimo recente con volumi in crescita, aumento l'esposizione.",
            "Volatilita' alta ma asimmetria favorevole: scommessa netta sulla crescita.",
        ],
        "sell_reasons": [
            "Incasso il guadagno: il movimento e' stato rapido e preferisco ridurre.",
            "Taglio la perdita in fretta, come da strategia.",
        ],
    },
    "Beta": {
        "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "SPY", "QQQ"],
        "cash_share": (0.10, 0.22),
        "trade_prob": 0.50,
        "take_profit": 0.10,
        "stop_loss": -0.10,
        "buy_reasons": [
            "Aggiungo una posizione di qualita' per bilanciare crescita e stabilita'.",
            "Ribilancio verso il peso obiettivo mantenendo una parte di liquidita'.",
            "Valutazione ragionevole per un'azienda solida: acquisto di dimensione moderata.",
        ],
        "sell_reasons": [
            "Riporto la posizione al peso obiettivo prendendo profitto parziale.",
            "La tesi e' cambiata: riduco l'esposizione.",
        ],
    },
    "Gamma": {
        "symbols": ["VTI", "SPY", "KO", "JNJ", "PG", "BND"],
        "cash_share": (0.05, 0.12),
        "trade_prob": 0.30,
        "take_profit": 0.15,
        "stop_loss": -0.15,
        "buy_reasons": [
            "Preservazione del capitale: acquisto graduale di un ETF diversificato.",
            "Titolo difensivo con dividendo stabile: piccola posizione.",
            "Mantengo una riserva di cassa elevata e aggiungo solo con calma.",
        ],
        "sell_reasons": [
            "Riduco leggermente per riportare il rischio al livello desiderato.",
        ],
    },
}


def session_times(now: datetime) -> list[datetime]:
    """Le sessioni dei giorni feriali degli ultimi DAYS giorni, fino a ora."""
    times = []
    for offset in range(DAYS, -1, -1):
        day = (now - timedelta(days=offset)).replace(minute=0, second=0, microsecond=0)
        if day.weekday() >= 5:
            continue
        for hour in SESSION_HOURS_UTC:
            moment = day.replace(hour=hour)
            if moment <= now:
                times.append(moment)
    return times


def average_cost(account: Account, symbol: str) -> float:
    buys = [t for t in account.transactions if t.symbol == symbol and t.quantity > 0]
    bought = sum(t.quantity for t in buys)
    return sum(t.price * t.quantity for t in buys) / bought if bought else 0.0


def portfolio_value(account: Account, when: datetime) -> float:
    return account.balance + sum(simulated_price(s, when) * q for s, q in account.holdings.items())


def stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M:%S")


def add_log(name: str, when: datetime, kind: str, message: str) -> None:
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT INTO logs (name, datetime, type, message) VALUES (?, ?, ?, ?)",
            (name.lower(), stamp(when), kind, message),
        )


def buy(account: Account, symbol: str, quantity: int, when: datetime, reason: str) -> None:
    price = simulated_price(symbol, when) * (1 + SPREAD)
    account.balance -= price * quantity
    account.holdings[symbol] = account.holdings.get(symbol, 0) + quantity
    account.transactions.append(
        Transaction(symbol=symbol, quantity=quantity, price=price, timestamp=stamp(when), rationale=reason)
    )
    add_log(account.name, when, "account", f"Bought {quantity} of {symbol}")


def sell(account: Account, symbol: str, quantity: int, when: datetime, reason: str) -> None:
    price = simulated_price(symbol, when) * (1 - SPREAD)
    account.balance += price * quantity
    account.holdings[symbol] -= quantity
    if account.holdings[symbol] == 0:
        del account.holdings[symbol]
    account.transactions.append(
        Transaction(symbol=symbol, quantity=-quantity, price=price, timestamp=stamp(when), rationale=reason)
    )
    add_log(account.name, when, "account", f"Sold {quantity} of {symbol}")


def run_session(account: Account, profile: dict, rng: random.Random, when: datetime) -> None:
    add_log(account.name, when, "trace", f"Started: {account.name}-trading")
    account.portfolio_value_time_series.append((stamp(when), portfolio_value(account, when)))

    if rng.random() < profile["trade_prob"]:
        # Vende per primo se un titolo in portafoglio ha raggiunto take-profit o stop-loss
        for symbol, quantity in list(account.holdings.items()):
            cost = average_cost(account, symbol)
            change = simulated_price(symbol, when) / cost - 1 if cost else 0
            if change >= profile["take_profit"] or change <= profile["stop_loss"]:
                sell(account, symbol, max(1, quantity // 2), when, rng.choice(profile["sell_reasons"]))
                break
        else:
            symbol = rng.choice(profile["symbols"])
            price = simulated_price(symbol, when) * (1 + SPREAD)
            budget = account.balance * rng.uniform(*profile["cash_share"])
            quantity = int(budget // price)
            if quantity >= 1:
                buy(account, symbol, quantity, when, rng.choice(profile["buy_reasons"]))

    account.portfolio_value_time_series.append((stamp(when), portfolio_value(account, when)))
    add_log(account.name, when, "trace", f"Ended: {account.name}-trading")


def seed() -> None:
    reset_traders()
    now = datetime.now(timezone.utc)
    with sqlite3.connect(DB) as conn:
        conn.execute("DELETE FROM logs")

    for name, profile in PROFILES.items():
        account = Account.get(name)
        rng = random.Random(f"demo:{name}")
        for when in session_times(now):
            run_session(account, profile, rng, when)
        account.save()
        value = portfolio_value(account, now)
        print(f"{name}: {len(account.transactions)} operazioni, valore ${value:,.0f}")


if __name__ == "__main__":
    seed()
