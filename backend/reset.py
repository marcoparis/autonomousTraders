"""Riporta i conti al capitale iniziale con la strategia scritta in traders.toml.

    uv run -m backend.reset

Cancella posizioni, operazioni, storico e log di tutti i trader configurati.
"""

from .accounts import Account
from .config import TRADERS
from .database import clear_logs, write_setting


def reset_traders() -> None:
    for trader in TRADERS:
        Account.get(trader.name).reset(trader.strategy)
        clear_logs(trader.name)
        write_setting(f"{trader.name.lower()}_next_mode", "trade")
        print(f"{trader.name}: conto azzerato")


if __name__ == "__main__":
    reset_traders()
