"""Prezzi di mercato reali da Massive (ex Polygon.io).

Serve MASSIVE_API_KEY. I piani piu' economici non danno l'ultimo scambio in tempo
reale: si prova dal dato migliore al peggiore (ultimo scambio, snapshot, chiusura
del giorno prima) e si ricorda il primo che il piano accetta.
"""

import os
import time

from dotenv import load_dotenv
from massive import RESTClient

load_dotenv(override=True)

massive_api_key = os.getenv("MASSIVE_API_KEY", "").strip() or None

# La dashboard interroga l'API ogni pochi secondi e il piano gratuito di Massive
# accetta poche richieste al minuto: prezzi e stato del mercato restano in cache.
PRICE_TTL_SECONDS = 60
MARKET_STATUS_TTL_SECONDS = 300
_price_cache: dict[str, tuple[float, float]] = {}
_market_status_cache: tuple[float, bool] | None = None


class MarketDataError(RuntimeError):
    pass


def _client() -> RESTClient:
    if not massive_api_key:
        raise MarketDataError("MASSIVE_API_KEY non impostata: i prezzi reali non sono disponibili")
    return RESTClient(massive_api_key)


def _last_trade(client: RESTClient, symbol: str) -> float:
    return float(client.get_last_trade(symbol).price)


def _snapshot(client: RESTClient, symbol: str) -> float:
    snapshot = client.get_snapshot_ticker("stocks", symbol)
    return float(snapshot.min.close or snapshot.prev_day.close)


def _previous_close(client: RESTClient, symbol: str) -> float:
    return float(client.get_previous_close_agg(symbol)[0].close)


_price_methods = [_last_trade, _snapshot, _previous_close]
_plan_tier = 0


def get_share_price(symbol: str) -> float:
    """Prezzo corrente di un titolo; solleva MarketDataError se non disponibile."""
    global _plan_tier
    symbol = symbol.strip().upper()
    cached = _price_cache.get(symbol)
    if cached and time.monotonic() - cached[0] < PRICE_TTL_SECONDS:
        return cached[1]

    client = _client()
    for tier in range(_plan_tier, len(_price_methods)):
        try:
            price = _price_methods[tier](client, symbol)
        except Exception:
            continue
        if price > 0:
            _plan_tier = tier
            _price_cache[symbol] = (time.monotonic(), price)
            return price
    raise MarketDataError(f"Nessun prezzo disponibile per {symbol}")


def is_market_open() -> bool:
    """True se la borsa USA e' aperta. Se Massive non risponde si assume chiusa."""
    global _market_status_cache
    if _market_status_cache and time.monotonic() - _market_status_cache[0] < MARKET_STATUS_TTL_SECONDS:
        return _market_status_cache[1]
    try:
        is_open = _client().get_market_status().market == "open"
    except Exception:
        return False
    _market_status_cache = (time.monotonic(), is_open)
    return is_open
