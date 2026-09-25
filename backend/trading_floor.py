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

# Pausa tra un trader e il successivo, per lasciar scorrere la finestra al minuto
# dei rate limit. Mettila a 0 se usi un modello a pagamento senza limiti stretti.
PAUSE_BETWEEN_TRADERS_SECONDS = int(os.getenv("PAUSE_BETWEEN_TRADERS_SECONDS", "30"))

# Un solo ciclo ed esci, invece del loop infinito. Serve al workflow GitHub
# Actions (.github/workflows/trading-cycle.yml): ogni esecuzione del job e' un
# processo a se', quindi e' quel job a fare da "scheduler" con un cron, non
# questo script. In locale lascialo a false.
RUN_ONCE = os.getenv("RUN_ONCE", "false").strip().lower() == "true"

names = ["Alpha", "Beta", "Gamma"]
lastnames = ["High Risk", "Medium Risk", "Low Risk"]

if USE_MANY_MODELS:
    model_names = [
        "gpt-5.5",
        "deepseek-v4-flash",
        "gemini-3.5-flash",
    ]
    short_model_names = ["GPT 5.5", "DeepSeek V4", "Gemini 3.5 Flash"]
else:
    # TRADER_MODEL permette di scegliere il modello senza toccare il codice,
    # es. "gemini-2.5-flash" (piano gratuito di Google AI Studio, vedi README).
    default_model = os.getenv("TRADER_MODEL", "gpt-5.4-mini").strip()
    model_names = [default_model] * len(names)
    # MODEL_LABEL cambia solo il nome mostrato in dashboard (es. "Simulato" nella demo)
    short_model_names = [os.getenv("MODEL_LABEL", "").strip() or default_model] * len(names)


def create_traders() -> List[Trader]:
    traders = []
    for name, lastname, model_name in zip(names, lastnames, model_names):
        traders.append(Trader(name, lastname, model_name))
    return traders


def _notify_cycle_results() -> None:
    """Legge i conti appena aggiornati e manda la classifica su ntfy."""
    rows = []
    for name in names:
        account = Account.get(name)
        value = account.calculate_portfolio_value()
        rows.append((name, value, account.calculate_profit_loss(value)))
    notify_cycle_summary(rows)


async def run_traders_in_sequence(traders: List[Trader]) -> None:
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
    if RUN_ONCE:
        print("RUN_ONCE=true: eseguo un solo ciclo ed esco")
    else:
        print(f"Starting scheduler to run every {RUN_EVERY_N_MINUTES} minutes")
    asyncio.run(run_every_n_minutes())
