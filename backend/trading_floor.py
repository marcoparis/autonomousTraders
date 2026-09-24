from .traders import Trader
from .accounts import Account
from .notifications import notify_cycle_summary
from typing import List
import asyncio
from .tracers import LogTracer
from agents import add_trace_processor
from .market import is_market_open
from dotenv import load_dotenv
import os

load_dotenv(override=True)

RUN_EVERY_N_MINUTES = int(os.getenv("RUN_EVERY_N_MINUTES", "60"))
RUN_EVEN_WHEN_MARKET_IS_CLOSED = (
    os.getenv("RUN_EVEN_WHEN_MARKET_IS_CLOSED", "false").strip().lower() == "true"
)
USE_MANY_MODELS = os.getenv("USE_MANY_MODELS", "false").strip().lower() == "true"

# Un solo ciclo ed esci, invece del loop infinito. Serve al workflow GitHub
# Actions (.github/workflows/trading-cycle.yml): ogni esecuzione del job e' un
# processo a se', quindi e' quel job a fare da "scheduler" con un cron, non
# questo script. In locale lascialo a false.
RUN_ONCE = os.getenv("RUN_ONCE", "false").strip().lower() == "true"

names = ["Warren", "George", "Ray", "Cathie"]
lastnames = ["Patience", "Bold", "Systematic", "Crypto"]

if USE_MANY_MODELS:
    model_names = [
        "gpt-5.5",
        "deepseek-v4-flash",
        "gemini-3.5-flash",
        "grok-4.3",
    ]
    short_model_names = ["GPT 5.5", "DeepSeek V4", "Gemini 3.5 Flash", "Grok 4.3"]
else:
    # TRADER_MODEL permette di scegliere il modello senza toccare il codice,
    # es. "gemini-2.5-flash" (piano gratuito di Google AI Studio, vedi README).
    default_model = os.getenv("TRADER_MODEL", "gpt-5.4-mini").strip()
    model_names = [default_model] * 4
    short_model_names = [default_model] * 4


def create_traders() -> List[Trader]:
    traders = []
    for name, lastname, model_name in zip(names, lastnames, model_names):
        traders.append(Trader(name, lastname, model_name))
    return traders


def _notify_cycle_results() -> None:
    """Legge i quattro conti appena aggiornati e manda la classifica su ntfy."""
    rows = []
    for name in names:
        account = Account.get(name)
        value = account.calculate_portfolio_value()
        rows.append((name, value, account.calculate_profit_loss(value)))
    notify_cycle_summary(rows)


async def run_every_n_minutes():
    add_trace_processor(LogTracer())
    traders = create_traders()
    while True:
        if RUN_EVEN_WHEN_MARKET_IS_CLOSED or is_market_open():
            await asyncio.gather(*[trader.run() for trader in traders])
            _notify_cycle_results()
        else:
            print("Market is closed, skipping run")

        if RUN_ONCE:
            break
        await asyncio.sleep(RUN_EVERY_N_MINUTES * 60)


if __name__ == "__main__":
    if RUN_ONCE:
        print("RUN_ONCE=true: eseguo un solo ciclo ed esco")
    else:
        print(f"Starting scheduler to run every {RUN_EVERY_N_MINUTES} minutes")
    asyncio.run(run_every_n_minutes())
