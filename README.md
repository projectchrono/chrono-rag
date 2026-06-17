# chrono-rag

A RAG application that acts as an oracle for users in Chrono Forums. Ask questions about [Chrono](https://github.com/projectchrono/chrono) and [PyChrono](https://github.com/projectchrono/pychrono-examples-9.0) and get LLM-generated answers backed by vector search over the codebase.

## API

The backend is a FastAPI server (`src/main.py`) running on `http://localhost:8000`.

### `POST /index`

Parses the repos directory, generates embeddings, and upserts all chunks into MongoDB. Run this once after cloning the data.

**Response**
```json
{ "chunks_indexed": 142 }
```

### `POST /search`

Runs a vector search over indexed chunks and returns an LLM-generated answer.

**Request**
```json
{ "query": "How do I create a rigid body in PyChrono?", "top_k": 5, "model": "claude-opus-4-8" }
```

**Response**
```json
{ "answer": "To create a rigid body..." }
```

`top_k` is optional (default: 5). `model` is optional — supported values are `"claude-opus-4-8"` (default) and `"gpt-4o-mini"`.

## Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) — runs the MongoDB Atlas local container
- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda or Anaconda) — manages the Python environment and PyChrono
- [Node.js](https://nodejs.org/) ≥ 18 — for the frontend
- Git

### 1. Clone the repository

```bash
git clone --recurse-submodules <repo-url>
cd chrono-rag
```

If you already cloned without `--recurse-submodules`, populate the PyChrono submodule:

```bash
git submodule update --init
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
OPENAI_API_KEY=<your-openai-api-key>
ANTHROPIC_API_KEY=<your-anthropic-api-key>
```

Both keys are required:
- `OPENAI_API_KEY` — used for generating embeddings (`text-embedding-3-small`) and the `gpt-4o-mini` model
- `ANTHROPIC_API_KEY` — used for the default inference model (`claude-opus-4-8`)

Optional overrides (paths default to the locations below, relative to the project root):

```
REPOS_DIR=./pychrono-examples-9.0
MBOX_PATH=./topics.mbox
```

`REPOS_DIR` points to the PyChrono examples directory (the submodule). If the directory does not exist, `POST /index` will clone it automatically from GitHub via HTTPS.

`MBOX_PATH` points to a Mbox export of the Chrono mailing list. This file is **not** included in the repository (it is in `.gitignore`). If it does not exist, the indexing step silently skips mailing-list data.

### 3. Start MongoDB Atlas local

The backend requires a MongoDB instance with Atlas Vector Search support. Run it via Docker:

```bash
docker pull mongodb/mongodb-atlas-local
docker run -d --name atlas_local --restart unless-stopped \
  -p 27017:27017 \
  -v atlas_data:/data/db \
  -v atlas_mongot_data:/data/mongot \
  mongodb/mongodb-atlas-local:latest
```

Verify the container is running:

```bash
docker ps --filter name=atlas_local
```

The backend connects to `mongodb://localhost:27017/?directConnection=true` and uses the database `chrono_rag`, collection `chunks`. No additional MongoDB configuration is required.

### 4. Create the Python environment

PyChrono must be installed from the `projectchrono` Conda channel; it is not available on PyPI.

```bash
conda create -n chrono python=3.12 -y
conda install -n chrono projectchrono::pychrono -c conda-forge -y
conda run -n chrono pip install -r requirements.txt
```

### 5. Start the backend

Run the FastAPI server from the project root:

```bash
conda run -n chrono python -m uvicorn main:app \
  --host 127.0.0.1 --port 8000 --reload --app-dir src
```

Wait until you see `Application startup complete.` in the output before proceeding.

### 6. Populate the vector store

Run this once to parse the PyChrono source files, generate embeddings, upsert them into MongoDB, and create the Atlas Vector Search index:

```bash
curl -s -X POST http://localhost:8000/index
```

The response reports how many chunks were indexed:

```json
{ "chunks_indexed": 142 }
```

This step can take several minutes depending on the size of the data. It is idempotent — running it again upserts the same documents and skips index creation if the index already exists.

### 7. Start the frontend

```bash
cd frontend && npm install && npm run dev
```

The app will be available at [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/search` requests to the backend at `http://localhost:8000`.

## Running (after initial setup)

Once set up, only steps 3, 5, and 7 are needed on subsequent runs:

**Start MongoDB** (skip if Docker container is already running with `--restart unless-stopped`):
```bash
docker start atlas_local
```

**Backend**
```bash
conda run -n chrono python -m uvicorn main:app \
  --host 127.0.0.1 --port 8000 --reload --app-dir src
```

**Frontend**
```bash
cd frontend && npm run dev
```
