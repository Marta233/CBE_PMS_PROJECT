# AI Objective Generator

Generate SMART objectives using:
- BSC
- Role
- Job Description

Powered by Ollama (free local LLM).

## Run with Docker

Upload and objective generation run in separate containers. A failed upload does not stop generation.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it.
2. Install [Ollama](https://ollama.com/) and pull the model named in `.env` (default `llama3`):

```bash
ollama pull llama3
```

3. Let Ollama accept connections from Docker. By default it only listens on this PC. Set the listen address, then restart Ollama:

```bash
# Windows PowerShell, then quit and start Ollama again
setx OLLAMA_HOST "0.0.0.0:11434"
```

4. From this folder, copy the env file and start the stack:

```bash
cp .env.example .env
docker compose up --build
```

5. Open [http://localhost:8080](http://localhost:8080).

The first start has an empty knowledge base. Upload BSC, job description, LOS, and work-plan files on the ingestion page. Generation keeps the previous index until you reload it:

```bash
curl -X POST http://localhost:8080/api/reload-index
```

Stop the stack with Ctrl+C, or `docker compose down` from another terminal. `docker compose down` keeps the uploaded files. `docker compose down -v` deletes them.

## Run without Docker

From `Back_End/`:

```bash
python run_app.py
```

That starts the API at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Upload and generation share one process. Redis is optional; without it, generation runs in the API process.

From `frontend/`:

```bash
npm install
npm run dev
```

The site calls `http://127.0.0.1:8000` unless you set `VITE_API_URL`.
