"""Prezzi azionari della DEMO: vengono sempre dal simulatore (market_simulator.py).

Nessuna chiave e nessuna rete. Per prezzi reali vedi il blocco "MODALITA' REALE" in
fondo al file e COME_RENDERLO_REALE.txt (punto 7).
"""

from .market_simulator import simulated_price

# Nella demo non c'e' nessuna chiave dati. L'API la legge per dire alla dashboard
# quale sorgente e' attiva ("simulator" oppure "massive").
massive_api_key = None


def get_share_price(symbol: str) -> float:
    """Prezzo corrente di un titolo (simulato, deterministico)."""
    return simulated_price(symbol)


def is_market_open() -> bool:
    """Nella demo il mercato risulta sempre aperto."""
    return True


# ---------------------------------------------------------------------------
# MODALITA' REALE (prezzi Massive, ex Polygon.io)
#
# Per attivarla: 1) uv add "massive>=2.8,<3"   2) MASSIVE_API_KEY nel .env
# 3) cancella le due funzioni demo qui sopra e la riga "massive_api_key = None",
# 4) togli il commento a tutto il blocco qui sotto. Senza chiave ricade da solo
# sul simulatore, quindi si puo' lasciare attivo anche senza MASSIVE_API_KEY.
# ---------------------------------------------------------------------------
#
# import os
# from dotenv import load_dotenv
# from massive import RESTClient
#
# load_dotenv(override=True)
#
# massive_api_key = os.getenv("MASSIVE_API_KEY")
#
#
# def _last_trade(client: RESTClient, symbol: str) -> float:
#     return float(client.get_last_trade(symbol).price)
#
#
# def _snapshot(client: RESTClient, symbol: str) -> float:
#     snapshot = client.get_snapshot_ticker("stocks", symbol)
#     return float(snapshot.min.close or snapshot.prev_day.close)
#
#
# def _previous_close(client: RESTClient, symbol: str) -> float:
#     return float(client.get_previous_close_agg(symbol)[0].close)
#
#
# # Best price first, prior close last. Lower tier plans reject the earlier calls,
# # so we remember the first tier that works and start there next time.
# price_methods = [_last_trade, _snapshot, _previous_close]
# plan_tier = 0
#
#
# def get_share_price(symbol: str) -> float:
#     """Return the current price for a symbol, from Massive or the simulator."""
#     if massive_api_key:
#         try:
#             return get_share_price_massive(symbol)
#         except Exception as e:
#             print(f"Massive API unavailable ({e}); using a simulated price")
#     return simulated_price(symbol)
#
#
# def get_share_price_massive(symbol: str) -> float:
#     """Best price the plan allows, remembering the working tier to avoid repeat failures."""
#     global plan_tier
#     client = RESTClient(massive_api_key)
#     for tier in range(plan_tier, len(price_methods)):
#         try:
#             price = price_methods[tier](client, symbol)
#             plan_tier = tier
#             return price
#         except Exception:
#             continue
#     raise RuntimeError(f"No Massive price available for {symbol}")
#
#
# def is_market_open() -> bool:
#     """Whether the US market is open; True on simulated data or if Massive is unreachable."""
#     if not massive_api_key:
#         return True
#     try:
#         client = RESTClient(massive_api_key)
#         return client.get_market_status().market == "open"
#     except Exception:
#         return True
