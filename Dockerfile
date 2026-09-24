# Immagine unica per il trading floor.
#
# Perche' serve Docker e non basta il runtime Python di un PaaS:
# il motore lancia i server MCP come sottoprocessi, e tre di questi
# girano su Node (npx tavily-mcp, npx mcp-memory-libsql) mentre altri
# usano uv/uvx. Un runtime "solo Python" non ha ne' npx ne' uv, quindi
# il Researcher parte senza ricerca web e senza memoria.
#
# Build:  docker build -t trading-floor .
# Run:    docker run --env-file .env -p 8000:8000 -v $(pwd)/data:/app/data trading-floor

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_MAJOR=20

# Node per i server MCP basati su npx, curl per installare uv
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg git build-essential \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# uv: usato sia per installare le dipendenze sia dai server MCP a runtime
RUN pip install uv

WORKDIR /app

# Dipendenze Python prima del codice, cosi' il layer resta in cache
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# Build del frontend: il risultato e' statico, Node serve solo qui
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend ./frontend
RUN cd frontend && npm run build

# Codice applicativo
COPY backend ./backend
COPY demo ./demo
COPY app.py ./

# accounts.db vive qui: montaci un volume o un disco persistente,
# altrimenti lo stato sparisce a ogni riavvio del container.
RUN mkdir -p /app/data
ENV ACCOUNTS_DB=/app/data/accounts.db

EXPOSE 8000

# Di default parte solo l'API. Il motore si lancia come comando separato:
#   docker run ... trading-floor python -m backend.trading_floor
# oppure con la lifespan di FastAPI (vedi README, opzione "processo unico").
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
