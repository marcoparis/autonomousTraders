# Autonomous Traders

Dashboard di una trading floor con tre trader che gestiscono ciascuno un portafoglio
azionario da 10.000 $: valore nel tempo, posizioni, operazioni e log dell'attività.

> **Questa è una demo.** Le operazioni, le motivazioni e i rendimenti sono
> **inventati**: li genera `backend/demo_seed.py` con regole semplici, senza nessun
> modello di linguaggio, e i prezzi vengono da un simulatore deterministico. Nessuna
> chiave API è necessaria. Non è un consiglio finanziario e non esegue ordini veri.
>
> Il progetto è nato come sistema di agenti LLM che ricercano notizie, decidono e
> operano da soli. Quella parte non è nel repo, ma `COME_RENDERLO_REALE.txt` contiene
> il codice completo e la guida per riattivarla.

## I tre trader

| Nome | Profilo | Strategia |
|---|---|---|
| Alpha | alto rischio | posizioni concentrate, titoli volatili e di crescita, momentum |
| Beta | rischio medio | portafoglio diversificato, mix di crescita e indici, liquidità moderata |
| Gamma | basso rischio | ETF diversificati e dividendi, molta liquidità, poche operazioni |

Le strategie iniziali stanno in `backend/reset.py`.

## Architettura

```
  backend/demo_seed.py      genera lo storico inventato
            |
            v
  data/accounts.db          SQLite: un conto JSON per trader + tabella log
            |
            v
  backend/api.py            FastAPI in sola lettura (/api/traders, /api/market, ...)
            |
            v
  frontend/                 Vite + TypeScript + uPlot, interroga l'API ogni pochi secondi
```

I prezzi arrivano da `backend/market_simulator.py`: deterministici, stessi valori a
parità di titolo e istante, quindi lo storico resta coerente con ciò che l'API mostra.

## Struttura

| Percorso | Cosa contiene |
|---|---|
| `backend/api.py` | endpoint HTTP in sola lettura |
| `backend/accounts.py` | modello del conto (saldo, posizioni, operazioni) |
| `backend/database.py` | lettura e scrittura su SQLite |
| `backend/demo_seed.py` | generatore dello storico simulato |
| `backend/reset.py` | azzera i conti e imposta le strategie iniziali |
| `backend/market.py`, `market_simulator.py` | prezzi (simulati) |
| `data/accounts.db` | database della demo, committato di proposito |
| `frontend/` | dashboard |
| `render.yaml` | deploy su Render (sito statico + API) |
| `tests/` | test del simulatore di prezzi |
| `COME_RENDERLO_REALE.txt` | guida e codice per passare ad agenti veri |

## Requisiti

- Python 3.12 o 3.13 e [uv](https://docs.astral.sh/uv/)
- Node 20+

## Provarlo in locale

```bash
uv sync
cd frontend && npm install && cd ..

uv run -m backend.demo_seed                      # facoltativo: rigenera i dati inventati
uv run python -m uvicorn backend.api:app --port 8000
```

In un secondo terminale:

```bash
cd frontend && npm run dev
```

Apri <http://localhost:5173>. In sviluppo Vite fa da proxy su `/api` verso la porta
8000, quindi non c'è CORS da gestire. La documentazione interattiva dell'API è su
<http://localhost:8000/docs>.

Test: `uv run pytest -q`

## Metterlo online (Render, gratis)

`render.yaml` crea due servizi: il frontend come Static Site e l'API come Web Service
free.

1. Pubblica il repo su GitHub.
2. Su render.com: **New → Blueprint**, collega il repo.
3. Dopo il primo deploy controlla in `render.yaml` che `ALLOWED_ORIGINS` (URL del
   sito statico) e `VITE_API_BASE` (URL dell'API) coincidano con gli URL assegnati da
   Render, poi fai push.

`autoDeploy` è attivo: ogni push aggiorna la demo. L'API free si addormenta dopo 15
minuti di inattività, e la prima richiesta dopo la pausa impiega circa un minuto.

Per cambiare i dati mostrati: `uv run -m backend.demo_seed`, poi commit e push di
`data/accounts.db`.

## Renderlo reale

Agenti LLM veri, prezzi reali, notifiche sul telefono e aggiornamento automatico con
GitHub Actions: tutto in `COME_RENDERLO_REALE.txt`, con i passi da seguire e il codice
del motore da ricopiare. Attenzione ai costi: ogni ciclo lancia tre agenti che fanno
più ricerche web.

## Licenza

MIT
