# Autonomous Traders

Tre agenti LLM gestiscono ciascuno un portafoglio azionario da 10.000 dollari.
Ricercano notizie sul web, consultano i prezzi, comprano, vendono e riscrivono la
propria strategia in base a come sono andati i trade precedenti. Tutti i loro
strumenti sono esposti attraverso server **MCP** (Model Context Protocol).

Una dashboard mostra in tempo reale valore del portafoglio, posizioni e il flusso
di ragionamento di ciascun agente.

---

## I tre trader

| Nome | Profilo | Strategia |
|---|---|---|
| Alpha | alto rischio | posizioni concentrate, titoli volatili e di crescita, momentum |
| Beta | rischio medio | portafoglio diversificato, mix di crescita e indici, liquidità moderata |
| Gamma | basso rischio | ETF diversificati e dividendi, molta liquidità, poche operazioni |

Le strategie iniziali stanno in `backend/reset.py`. Gli agenti hanno un tool
`change_strategy`: dopo qualche ciclo il testo che leggi nella dashboard non è
più quello di partenza, l'hanno riscritto loro.

## Architettura

```
  backend/trading_floor.py          il motore: ogni N minuti lancia i 3 trader
            |
            |  per ogni trader, 6 server MCP come sottoprocessi (stdio)
            v
  accounts_server   market_server   push_server   fetch   tavily   memory
     (conti)          (prezzi)        (ntfy)     (web)  (ricerca)  (grafo)
            |
            v
     accounts.db  (SQLite: conti come JSON + tabella log)
            |
     +------+------------------+
     |                         |
  backend/api.py          app.py  (dashboard Gradio, legge il db in-process)
  (FastAPI read-only)
     |
     v
  frontend/  (Vite + TypeScript + uPlot, polling ogni 2-6 s)
```

Il motore e le interfacce non si parlano mai direttamente: comunicano solo
attraverso il database. Puoi spegnere la dashboard senza fermare il trading, e
viceversa.

## Stack

| Livello | Tecnologia |
|---|---|
| Runtime agenti | OpenAI Agents SDK (`Agent`, `Runner`, `trace`, `TracingProcessor`) |
| Protocollo tool | MCP, trasporto stdio, `FastMCP` per i server e `MCPServerStdio` lato client |
| Modelli | OpenAI, con router opzionale verso DeepSeek, Gemini, Grok e OpenRouter |
| Dati di mercato | Massive (ex Polygon.io), con simulatore deterministico come fallback |
| Persistenza | SQLite |
| API | FastAPI + Uvicorn |
| Frontend | Vite, TypeScript stretto, uPlot, CSS custom properties, zero framework |
| Dashboard alt. | Gradio + Plotly + pandas |
| Notifiche | ntfy.sh |
| Concorrenza | `asyncio.gather`, `AsyncExitStack` |

## Requisiti

- Python 3.12 o 3.13
- Node 20+ (serve a `npx`, che lancia due dei server MCP)
- [uv](https://docs.astral.sh/uv/)
- Una chiave OpenAI. Le altre sono tutte opzionali.

## Installazione

```bash
git clone https://github.com/<tuo-utente>/autonomous-traders.git
cd autonomous-traders

uv sync
cd frontend && npm install && cd ..

cp .env.example .env     # poi apri .env e metti la chiave OpenAI
```

## Esecuzione

Servono tre terminali. L'ordine conta poco, ma il motore per ultimo è più
comodo: vedi la dashboard popolarsi mentre gli agenti lavorano.

**1. API**

```bash
uv run uvicorn backend.api:app --port 8000
```

Documentazione interattiva su <http://localhost:8000/docs>.

**2. Frontend**

```bash
cd frontend && npm run dev
```

Apri <http://localhost:5173>. In sviluppo Vite fa da proxy su `/api` verso la
porta 8000, quindi il browser vede una sola origine e non c'è CORS da gestire.

**3. Motore**

```bash
uv run -m backend.trading_floor
```

Per azzerare i conti e ripartire dalle strategie iniziali:

```bash
uv run -m backend.reset
```

Dashboard Gradio alternativa, se preferisci quella al frontend Vite:

```bash
uv run app.py
```

Test:

```bash
uv run pytest -q
```

## Costi

Ogni ciclo lancia tre agenti, ognuno con un sub-agente ricercatore che fa più
ricerche web. Con `RUN_EVERY_N_MINUTES=60` sono 72 esecuzioni di agente al giorno.
Tienilo presente prima di lasciarlo acceso una notte. In sviluppo alza
l'intervallo, e ricorda che senza `MASSIVE_API_KEY` i prezzi arrivano dal
simulatore a costo zero.

## Notifiche con ntfy.sh

1. Installa l'app ntfy (Android / iOS) o apri <https://ntfy.sh/app>.
2. Iscriviti a un topic lungo e non indovinabile, es. `trading-floor-7g2k9x`.
3. Mettilo in `.env` come `NTFY_TOPIC`.
4. Prova: `uv run -m backend.notifications`.

Il topic è pubblico: chiunque lo conosca legge e scrive. Usa un nome casuale.

Arrivano tre tipi di notifica: il riepilogo che ogni trader manda a fine sessione
(tool MCP `push`), la classifica di fine ciclo, e un alert se un trader va in
errore.

## Deploy

Il progetto è composto da tre processi, e uno dei tre lancia sottoprocessi Node.
Questo rende il deploy meno banale di una normale web app. Tre strade, dalla più
semplice alla più costosa.

### 1. Vetrina statica (zero configurazione)

Frontend e API online, motore fermo. `render.yaml` fa tutto: static site
gratis per il frontend, web service free per l'API in sola lettura.

```bash
uv run -m backend.reset                       # strategie iniziali
ACCOUNTS_DB=data/accounts.db uv run -m backend.trading_floor   # un po' di cicli, poi Ctrl+C
git add data/accounts.db && git commit -m "Dati demo"
```

La demo pubblicata usa dati **simulati**, generati senza nessun modello da
`backend/demo_seed.py` con il simulatore di prezzi: operazioni, motivazioni e
rendimenti sono inventati e servono solo a mostrare la dashboard. Per rigenerarli:

```bash
ACCOUNTS_DB=data/accounts.db uv run -m backend.demo_seed
```

Il badge in alto nella dashboard dice "Simulated". Con un modello vero
(vedi `TRADER_MODEL` in `.env.example`) e il motore acceso i dati diventano quelli
prodotti dagli agenti.

### 2. Vetrina che si aggiorna da sola (ancora gratis)

Uguale alla 1, più `.github/workflows/trading-cycle.yml`: un cron di GitHub
Actions esegue un ciclo di trading ogni ora, scrive `data/accounts.db` e lo
ricommitta. Render ha `autoDeploy: true`, quindi ogni commit aggiorna l'API in
automatico. Nessun server acceso: il "motore" è il runner temporaneo di GitHub
Actions, gratuito senza limiti sui repo pubblici.

Setup: aggiungi `OPENAI_API_KEY`, `TAVILY_API_KEY`, `NTFY_TOPIC` (facoltativa)
come Repository secrets (Settings → Secrets and variables → Actions), e in
Settings → Actions → General abilita "Read and write permissions" per i
workflow, altrimenti il job non può ricommittare.

Limite onesto: aggiornamento orario, non in tempo reale, e ogni ciclo produce
un commit binario. Per un progetto dimostrativo è un compromesso ragionevole.

### 3. Sistema sempre vivo (a pagamento)

Serve il `Dockerfile` (Python, Node e uv nella stessa immagine) e un host
sempre acceso con disco persistente: su Render lo Starter a 7$/mese più il
disco a 0,25$/GB, oppure un VPS piccolo con Docker. Il piano free di Render non
basta per il motore continuo: i background worker non hanno un tipo di
istanza gratuito, il filesystem è effimero e i servizi free si addormentano
dopo 15 minuti di inattività. Il costo dominante comunque non è l'host, sono i
token: un motore sempre acceso richiama gli agenti a ogni ciclo, 24 ore su 24.

## Limiti noti

- Un ciclo apre circa 18 sottoprocessi MCP (6 per trader). Funziona bene su un
  portatile, molto meno su un'istanza da 512 MB.
- SQLite con un processo che scrive e due che leggono: abilita il journal WAL se
  vedi errori "database is locked".
- I prezzi del simulatore sono verosimili ma inventati. Con `MASSIVE_API_KEY`
  diventano reali.
- Non è un consiglio finanziario e non esegue ordini veri.

## Licenza

MIT
