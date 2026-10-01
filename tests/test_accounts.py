import pytest

from backend import accounts
from backend.accounts import SPREAD, Account
from backend.config import INITIAL_BALANCE

PRICES = {"AAPL": 200.0, "MSFT": 400.0}


@pytest.fixture(autouse=True)
def fake_market(monkeypatch):
    monkeypatch.setattr(accounts, "get_share_price", lambda symbol: PRICES[symbol])
    monkeypatch.setattr(accounts, "notify_trade", lambda *args, **kwargs: None)


@pytest.fixture
def account():
    acc = Account.get("tester")
    acc.reset("test strategy")
    return acc


def test_new_account_starts_with_initial_balance(account):
    assert account.balance == INITIAL_BALANCE
    assert account.holdings == {}


def test_buy_applies_spread_and_updates_balance(account):
    account.buy_shares("aapl", 10, "test")
    assert account.holdings == {"AAPL": 10}
    assert account.balance == pytest.approx(INITIAL_BALANCE - 10 * 200 * (1 + SPREAD))


def test_sell_closes_position(account):
    account.buy_shares("AAPL", 5, "test")
    account.sell_shares("AAPL", 5, "test")
    assert "AAPL" not in account.holdings
    assert account.transactions[-1].quantity == -5


@pytest.mark.parametrize("quantity", [0, -3, 2.5])
def test_rejects_non_positive_or_fractional_quantities(account, quantity):
    with pytest.raises(ValueError):
        account.buy_shares("AAPL", quantity, "test")
    with pytest.raises(ValueError):
        account.sell_shares("AAPL", quantity, "test")
    assert account.balance == INITIAL_BALANCE


def test_cannot_overspend_or_oversell(account):
    with pytest.raises(ValueError):
        account.buy_shares("MSFT", 1000, "too big")
    with pytest.raises(ValueError):
        account.sell_shares("MSFT", 1, "not held")


def test_profit_and_loss_follow_the_price(account, monkeypatch):
    account.buy_shares("AAPL", 10, "test")
    monkeypatch.setattr(accounts, "get_share_price", lambda symbol: 220.0)
    value = account.calculate_portfolio_value()
    expected_pnl = 10 * 220 - 10 * 200 * (1 + SPREAD)
    assert account.calculate_profit_loss(value) == pytest.approx(expected_pnl)


def test_state_is_persisted(account):
    account.buy_shares("AAPL", 2, "test")
    assert Account.get("tester").holdings == {"AAPL": 2}
