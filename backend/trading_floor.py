import asyncio
import os
from typing import List

from agents import add_trace_processor
from dotenv import load_dotenv

from .accounts import Account
from .config import TRADERS
from .market import is_market_open
from .notifications import notify_cycle_summary
from .tracers import LogTracer
from .traders import Trader

load_dotenv(override=True)

RUN_EVERY_N_MINUTES = int(os.getenv("RUN_EVERY_N_MINUTES", "60"))
RUN_EVEN_WHEN_MARKET_IS_CLOSED = (
    os.getenv("RUN_EVEN_WHEN_MARKET_IS_CLOSED", "false").strip().lower() == "true"
)
# Pausa tra un trader e il successivo, per lasciar scorrere la finestra al minuto
# dei rate limit. Mettila a 0 se usi un modello a pagamento senza limiti stretti.
PAUSE_BETWEEN_TRADERS_SECONDS = int(os.getenv("PAUSE_BETWEEN_TRADERS_SECONDS", "30"))

# Un solo ciclo ed esci, invece del loop infinito. Serve al workflow GitHub
# Actions (.github/workflows/trading-cycle.yml): ogni esecuzione del job e' un
# processo a se', quindi e' quel job a fare da "scheduler" con un cron, non
# questo script. In locale lascialo a false.
RUN_ONCE = os.getenv("RUN_ONCE", "false").strip().lower() == "true"


REQUIRED_KEYS = {
    "MASSIVE_API_KEY": "prezzi di mercato reali",
    "TAVILY_API_KEY": "ricerca web del researcher",
}


def check_required_keys() -> None:
    """Si ferma subito se manca una chiave indispensabile, prima di spendere crediti."""
    missing = [f"{key} ({why})" for key, why in REQUIRED_KEYS.items() if not os.getenv(key)]
    if missing:
        raise SystemExit("Chiavi mancanti nel .env: " + ", ".join(missing))


def create_traders() -> list[Trader]:
    return [Trader(t.name, t.profile, t.model) for t in TRADERS]


def _notify_cycle_results() -> None:
    """Legge i conti appena aggiornati e manda la classifica su ntfy."""
    rows = []
    for trader in TRADERS:
        account = Account.get(trader.name)
        try:
            value = account.calculate_portfolio_value()
        except Exception as e:
            print(f"Valore di {trader.name} non calcolabile: {e}")
            continue
        rows.append((trader.name, value, account.calculate_profit_loss(value)))
    notify_cycle_summary(rows)


async def run_traders_in_sequence(traders: list[Trader]) -> None:
    """Un trader alla volta, con una pausa in mezzo.

    In parallelo i tre agenti sommano le loro richieste e sforano subito i limiti
    dei piani gratuiti (es. 15 richieste/minuto su Gemini Flash Lite, 8K token/minuto
    su Groq). In sequenza un ciclo dura di piu', ma resta dentro le quote.
    """
    for index, trader in enumerate(traders):
        if index and PAUSE_BETWEEN_TRADERS_SECONDS:
            await asyncio.sleep(PAUSE_BETWEEN_TRADERS_SECONDS)
        await trader.run()


async def run_every_n_minutes():
    add_trace_processor(LogTracer())
    traders = create_traders()
    while True:
        if RUN_EVEN_WHEN_MARKET_IS_CLOSED or is_market_open():
            await run_traders_in_sequence(traders)
            _notify_cycle_results()
        else:
            print("Market is closed, skipping run")

        if RUN_ONCE:
            break
        await asyncio.sleep(RUN_EVERY_N_MINUTES * 60)


if __name__ == "__main__":
    check_required_keys()
    if RUN_ONCE:
        print("RUN_ONCE=true: eseguo un solo ciclo ed esco")
    else:
        print(f"Starting scheduler to run every {RUN_EVERY_N_MINUTES} minutes")
    asyncio.run(run_every_n_minutes())
