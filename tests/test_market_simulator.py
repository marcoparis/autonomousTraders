"""
Test del simulatore di prezzi.

E' l'unico modulo del progetto completamente deterministico e privo di
dipendenze esterne: nessuna chiave API, nessuna rete, nessun database.
Per questo e' il punto giusto dove mettere dei test veri.

Esegui con:  uv run pytest -q
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.market_simulator import EPOCH, SWING, simulated_price

NOON = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def test_price_is_deterministic():
    """Stesso ticker e stesso istante devono dare sempre lo stesso prezzo:
    e' la proprieta' che rende il simulatore utilizzabile al posto di un'API."""
    assert simulated_price("AAPL", NOON) == simulated_price("AAPL", NOON)


def test_different_tickers_give_different_prices():
    prices = {simulated_price(t, NOON) for t in ["AAPL", "MSFT", "NVDA", "TSLA"]}
    assert len(prices) == 4


def test_ticker_is_case_insensitive():
    assert simulated_price("aapl", NOON) == simulated_price("AAPL", NOON)


def test_price_is_positive():
    for ticker in ["AAPL", "MSFT", "NVDA", "SPY", "QQQ", "ZZZZ"]:
        assert simulated_price(ticker, NOON) > 0


def test_price_stays_within_the_configured_swing():
    """Il prezzo oscilla attorno a una base tra 20 e 499, entro +/- SWING."""
    for ticker in ["AAPL", "MSFT", "NVDA", "SPY"]:
        for days in range(0, 400, 17):
            when = EPOCH + timedelta(days=days)
            price = simulated_price(ticker, when)
            assert 20 * (1 - SWING) <= price <= 500 * (1 + SWING)


def test_price_moves_smoothly_over_an_hour():
    """Un'ora di differenza non deve produrre un salto: il rumore e'
    interpolato, non casuale a ogni chiamata."""
    later = NOON + timedelta(hours=1)
    base = simulated_price("AAPL", NOON)
    assert abs(simulated_price("AAPL", later) - base) / base < 0.05


def test_price_actually_moves_over_a_month():
    """Deve pero' muoversi: un prezzo piatto non simulerebbe nulla."""
    later = NOON + timedelta(days=30)
    assert simulated_price("AAPL", later) != simulated_price("AAPL", NOON)


def test_price_is_rounded_to_cents():
    price = simulated_price("AAPL", NOON)
    assert price == round(price, 2)


@pytest.mark.parametrize("ticker", ["AAPL", "BRK.B", "SPY"])
def test_default_timestamp_is_now(ticker):
    """Chiamato senza istante usa l'ora corrente e non esplode."""
    assert simulated_price(ticker) > 0
