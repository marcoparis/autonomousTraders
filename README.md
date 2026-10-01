# Autonomous Traders

Tre agenti AI che gestiscono ognuno un portafoglio azionario e decidono da soli cosa comprare e vendere. Ogni ciclo un agente legge le notizie, controlla i prezzi reali di borsa, rivede la propria strategia ed esegue le operazioni. Una dashboard mostra in tempo reale valore dei portafogli, posizioni e attività.

Dashboard: https://trading-floor-s5tt.onrender.com/

I conti sono virtuali: gli agenti operano con prezzi veri ma senza muovere soldi reali. Non è un consiglio finanziario.

## Come funziona

Ogni trader è un agente dell'OpenAI Agents SDK con tre server MCP:

- `accounts_server`: legge il conto, compra, vende e cambia strategia
- il server ufficiale di Massive (ex Polygon.io) per prezzi, indicatori e fondamentali
- `push_server`: manda una notifica sul telefono a fine sessione

Al trader è collegato un secondo agente, il researcher, usato come strumento. Cerca notizie con Tavily, legge le pagine web e conserva quello che impara in una memoria che resta da un ciclo all'altro.

I cicli si alternano: in uno il trader cerca nuove opportunità, in quello dopo ribilancia il portafoglio. Lo stato dei conti sta in SQLite (`data/accounts.db`). L'API FastAPI lo legge e la dashboard (Vite + TypeScript) lo interroga ogni pochi secondi.

```
GitHub Actions (cron) ──> backend/trading_floor.py ──> agenti + server MCP
                                    │
                                    v
                            data/accounts.db  ──commit──>  Render: API + dashboard
```

## Configurare i bot

I trader sono definiti in `traders.toml`: nome, profilo, modello e strategia iniziale. Per aggiungere un trader basta copiare un blocco `[[trader]]`; dashboard, API e motore lo leggono da lì.

```toml
[[trader]]
name = "Alpha"
profile = "High Risk"
model = "gpt-5.4-mini"        # facoltativo, altrimenti vale TRADER_MODEL
strategy = """You are Alpha, a HIGH-RISK trader. ..."""
```

Dopo aver cambiato i trader, `uv run -m backend.reset` riporta tutti i conti al capitale iniziale (`initial_balance`, sempre in `traders.toml`).

Il modello si sceglie dal nome: `gpt-...` usa OpenAI, `gemini-...` Google, `deepseek-...` DeepSeek, `grok-...` xAI, `groq:...` Groq, `provider/modello` OpenRouter. Ogni provider vuole la sua chiave nel `.env`.

## Chiavi necessarie

- `OPENAI_API_KEY`, o la chiave del provider scelto
- `MASSIVE_API_KEY` per i prezzi (massive.com, c'è un piano gratuito con limiti stretti)
- `TAVILY_API_KEY` per la ricerca web (1000 crediti gratuiti al mese)
- `NTFY_TOPIC` se vuoi le notifiche sul telefono (facoltativa)

Tutte le variabili sono descritte in `.env.example`. Se manca una chiave obbligatoria il motore si ferma subito, prima di spendere crediti.

## Avvio in locale

Servono Python 3.12+, [uv](https://docs.astral.sh/uv/) e Node 20+ (alcuni server MCP girano con `npx`).

```bash
uv sync
cp .env.example .env          # poi inserisci le chiavi

uv run -m backend.reset       # conti puliti
uv run -m backend.trading_floor
```

Il motore gira ogni `RUN_EVERY_N_MINUTES` minuti, solo a borsa aperta, a meno di `RUN_EVEN_WHEN_MARKET_IS_CLOSED=true`. Con `RUN_ONCE=true` fa un solo ciclo ed esce.

Dashboard, in altri due terminali:

```bash
uv run python -m uvicorn backend.api:app --port 8000
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Test: `uv run --extra dev pytest`

## Online

Su Render girano solo API e dashboard (`render.yaml`). Il motore non sta sul piano gratuito: ha bisogno di Node, uv e di circa 18 sottoprocessi a ciclo. Lo fa girare GitHub Actions con `.github/workflows/trading-cycle.yml`. Il workflow esegue un ciclo, committa il database aggiornato e Render ripubblica la dashboard.

Per attivarlo:

1. In Settings → Secrets and variables → Actions aggiungi le chiavi come secrets (`OPENAI_API_KEY`, `MASSIVE_API_KEY`, `TAVILY_API_KEY`, `NTFY_TOPIC`) e, se vuoi, la variabile `TRADER_MODEL`.
2. In Settings → Actions → General imposta "Read and write permissions".
3. Prova con "Run workflow" dalla tab Actions; se va, togli il commento al `schedule` nel workflow per avere due cicli al giorno.

Su Render conviene impostare `MASSIVE_API_KEY` anche nel servizio `trading-floor-api`, così la dashboard mostra i prezzi correnti. Senza, valuta le posizioni all'ultimo prezzo scambiato.

Per un motore sempre acceso c'è il `Dockerfile`, da usare su un host a pagamento o una VPS.

## Costi

Il costo vero sono i token del modello: ogni ciclo lancia un agente per trader, e ogni agente fa diverse ricerche web. Conviene fare un ciclo di prova e controllare la spesa sulla console del provider prima di attivare il cron.

## Struttura

```
traders.toml              i bot: nomi, modelli, strategie
backend/trading_floor.py  il motore: un ciclo per tutti i trader
backend/traders.py        l'agente trader e il researcher
backend/templates.py      istruzioni e messaggi degli agenti
backend/mcp_servers.py    quali server MCP usa ogni agente
backend/accounts.py       il conto: comprare, vendere, valore, profitti
backend/accounts_server.py / push_server.py   i server MCP del progetto
backend/market.py         prezzi reali da Massive, con cache
backend/notifications.py  notifiche ntfy
backend/api.py            API in sola lettura per la dashboard
frontend/                 dashboard
tests/                    test di conti, configurazione e API
```

## Licenza

MIT
