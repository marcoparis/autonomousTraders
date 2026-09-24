"""
Notifiche push via ntfy.sh per il trading floor.

Perche' ntfy invece di Pushover:
    Pushover richiede un account, una app a pagamento e due credenziali
    (user key + application token). ntfy non richiede nulla: pubblichi su un
    topic con una POST HTTP e chiunque sia iscritto a quel topic la riceve.
    Per un progetto che si deve poter clonare ed eseguire in cinque minuti
    e' la scelta giusta.

Cosa notifica questo modulo:
    1. il riepilogo che ogni trader invia a fine sessione (tool MCP "push")
    2. la classifica di fine ciclo, con il valore di portafoglio di tutti
    3. gli errori di un trader, che altrimenti finirebbero solo in un print

Il punto 2 e' quello che conta davvero: il motore gira in loop ogni
RUN_EVERY_N_MINUTES e consuma crediti LLM mentre nessuno guarda. La push di
fine ciclo ti dice cosa e' successo senza tenere aperta la dashboard.

Configurazione (.env):
    NTFY_TOPIC       obbligatoria per abilitare le notifiche
    NTFY_SERVER      opzionale, default https://ntfy.sh
    NTFY_TOKEN       opzionale, Bearer token se il topic e' protetto
    DASHBOARD_URL    opzionale, link aperto al tap sulla notifica

Principio: una notifica non deve MAI far fallire un run.
Tutto e' dentro try/except con timeout.
"""

from __future__ import annotations

import os
from typing import Iterable, Optional, Sequence

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

DEFAULT_SERVER = "https://ntfy.sh"
TIMEOUT_SECONDS = 5

# Un'emoji per trader, cosi' si riconosce il mittente dalla notifica.
TRADER_TAGS = {
    "alpha": "rocket",
    "beta": "balance_scale",
    "gamma": "shield",
}


# --------------------------------------------------------------------------
# Configurazione
# --------------------------------------------------------------------------

def _topic() -> str:
    return (os.getenv("NTFY_TOPIC") or "").strip()


def _server() -> str:
    return (os.getenv("NTFY_SERVER") or DEFAULT_SERVER).rstrip("/")


def _dashboard_url() -> Optional[str]:
    url = (os.getenv("DASHBOARD_URL") or "").strip()
    return url or None


def is_enabled() -> bool:
    """True se NTFY_TOPIC e' configurato. Senza topic il motore gira lo stesso."""
    return bool(_topic())


# --------------------------------------------------------------------------
# Helper
# --------------------------------------------------------------------------

def _ascii_header(value: str) -> str:
    """
    Gli header HTTP devono essere latin-1: emoji e a capo li rompono.
    Il corpo viaggia in UTF-8, quindi le emoji nel testo vanno bene.
    Per le emoji nel titolo si usa l'header Tags con gli shortcode.
    """
    cleaned = value.replace("\n", " ").replace("\r", " ").strip()
    return cleaned.encode("latin-1", "ignore").decode("latin-1")


def _money(value: float) -> str:
    return f"${value:,.0f}"


# --------------------------------------------------------------------------
# API generica
# --------------------------------------------------------------------------

def notify(
    message: str,
    *,
    title: Optional[str] = None,
    priority: str = "default",
    tags: Optional[Iterable[str]] = None,
    click: Optional[str] = None,
    markdown: bool = False,
) -> bool:
    """
    Pubblica un messaggio sul topic ntfy configurato.

    Args:
        message:  corpo della notifica (UTF-8, multilinea ammesso)
        title:    titolo in grassetto
        priority: min | low | default | high | urgent
        tags:     shortcode emoji, es. ["chart_with_upwards_trend"]
        click:    URL aperto al tap; default DASHBOARD_URL
        markdown: chiede a ntfy di interpretare il body come Markdown

    Returns:
        True se accettata, False in ogni altro caso.
    """
    topic = _topic()
    if not topic:
        return False

    headers = {"Priority": priority}

    if title:
        headers["Title"] = _ascii_header(title)
    if tags:
        headers["Tags"] = _ascii_header(",".join(tags))
    if markdown:
        headers["Markdown"] = "yes"

    target = click or _dashboard_url()
    if target:
        headers["Click"] = _ascii_header(target)

    token = (os.getenv("NTFY_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.post(
            f"{_server()}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 - mai far fallire il trading per una push
        print(f"[ntfy] notifica non inviata: {exc}", flush=True)
        return False


# --------------------------------------------------------------------------
# Notifiche di dominio
# --------------------------------------------------------------------------

def notify_trader_push(message: str, trader: Optional[str] = None) -> bool:
    """
    Riepilogo inviato da un trader a fine sessione, via tool MCP "push".

    Il nome del trader e' opzionale: se il modello non lo passa, la notifica
    parte comunque con un titolo generico.
    """
    name = (trader or "").strip()
    tag = TRADER_TAGS.get(name.lower(), "speech_balloon")
    title = f"{name.title()} ha operato" if name else "Trading floor"
    return notify(message, title=title, priority="default", tags=[tag])


def notify_trade(
    trader: str,
    side: str,
    symbol: str,
    quantity: int,
    price: float,
    rationale: str,
    balance: float,
) -> bool:
    """
    Notifica per una singola operazione eseguita da un trader.

    Args:
        side:      "buy" o "sell"
        price:     prezzo unitario di esecuzione (spread incluso)
        rationale: la motivazione che il trader ha dichiarato
        balance:   liquidita' rimasta dopo l'operazione
    """
    buying = side == "buy"
    verb = "Acquisto" if buying else "Vendita"
    total = price * quantity
    reason = " ".join((rationale or "").split())
    if len(reason) > 400:
        reason = reason[:397] + "..."

    lines = [
        f"{verb} di {quantity} {symbol} a ${price:,.2f} (totale {_money(total)})",
        f"Liquidita' residua: {_money(balance)}",
    ]
    if reason:
        lines.append(f"Motivo: {reason}")

    return notify(
        "\n".join(lines),
        title=f"{trader}: {verb.lower()} {symbol}",
        priority="default",
        tags=[TRADER_TAGS.get(trader.lower(), "speech_balloon")],
    )


def notify_cycle_summary(rows: Sequence[tuple[str, float, float]]) -> bool:
    """
    Classifica di fine ciclo.

    Args:
        rows: sequenza di (nome, valore_portafoglio, pnl), in qualsiasi ordine.
    """
    if not rows:
        return False

    ranked = sorted(rows, key=lambda r: r[1], reverse=True)
    lines = []
    for position, (name, value, pnl) in enumerate(ranked, start=1):
        sign = "+" if pnl >= 0 else "-"
        lines.append(f"{position}. {name}: {_money(value)} ({sign}{_money(abs(pnl))})")

    leader = ranked[0][0]
    body = "\n".join(lines)

    return notify(
        body,
        title=f"Ciclo completato, in testa {leader}",
        priority="low",
        tags=["bar_chart"],
    )


def notify_trader_error(trader: str, error: BaseException | str) -> bool:
    """Un trader e' andato in errore. Priorita' alta: di solito e' una chiave
    scaduta, un rate limit o un server MCP che non parte."""
    return notify(
        f"{trader} ha interrotto il run.\n\n{error}",
        title=f"Errore su {trader}",
        priority="high",
        tags=["rotating_light"],
    )


if __name__ == "__main__":
    # Test manuale:  uv run -m backend.notifications
    if not is_enabled():
        print("NTFY_TOPIC non configurato: niente da testare.")
    else:
        ok = notify(
            "Se leggi questo sul telefono, ntfy e' configurato correttamente.",
            title="Trading floor: test",
            tags=["test_tube"],
        )
        print("Notifica inviata." if ok else "Invio fallito.")
