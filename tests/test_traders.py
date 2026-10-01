import asyncio

from backend import traders
from backend.traders import Trader


def test_trade_and_rebalance_alternate_across_runs(monkeypatch):
    """Each run is a fresh process on GitHub Actions: the mode must come from the database."""
    modes = []

    async def fake_run_with_trace(self):
        modes.append("trade" if self.do_trade else "rebalance")

    monkeypatch.setattr(Trader, "run_with_trace", fake_run_with_trace)
    monkeypatch.setattr(traders, "notify_trader_error", lambda *a: None)

    for _ in range(3):
        asyncio.run(Trader("Zeta").run())  # a new object every time, like a new process

    assert modes == ["trade", "rebalance", "trade"]
