from fastapi.testclient import TestClient

from backend import accounts, api, market
from backend.accounts import Account


def test_roster_comes_from_config():
    client = TestClient(api.app)
    names = [t["name"] for t in client.get("/api/traders").json()]
    assert names == ["Alpha", "Beta", "Gamma"]


def test_holdings_fall_back_to_last_trade_price(monkeypatch):
    monkeypatch.setattr(accounts, "get_share_price", lambda symbol: 100.0)
    monkeypatch.setattr(accounts, "notify_trade", lambda *a, **k: None)
    alpha = Account.get("Alpha")
    alpha.reset("s")
    alpha.buy_shares("NVDA", 3, "test")

    def unavailable(symbol):
        raise market.MarketDataError("no key")

    monkeypatch.setattr(market, "get_share_price", unavailable)
    data = TestClient(api.app).get("/api/traders/alpha").json()
    holding = data["holdings"][0]
    assert holding["symbol"] == "NVDA"
    assert holding["price"] == alpha.transactions[-1].price


def test_unknown_trader_is_404():
    assert TestClient(api.app).get("/api/traders/nobody").status_code == 404
