# chrono-rag

A RAG application that acts as an oracle for users in Chrono Forums. Ask questions about [Chrono](https://github.com/projectchrono/chrono) and [PyChrono](https://github.com/projectchrono/pychrono-examples-9.0) and get LLM-generated answers backed by vector search over the codebase.

---

## Quick Start (Linux — Ubuntu 22.04)

Clone the repo and run the setup script. It installs all dependencies, starts MongoDB, indexes the data, and launches the app.

```bash
git clone --recurse-submodules <repo-url>
cd chrono-rag
cp .env.example .env        # add your API keys
bash setup.sh
```

The script is safe to re-run — each step checks before acting. Once complete, the app is available at **https://localhost:5173**.

> **API keys required** — edit `.env` before running:
> ```
> OPENAI_API_KEY=<your-openai-api-key>
> ANTHROPIC_API_KEY=<your-anthropic-api-key>
> ```

---

## Manual Setup (macOS / Windows)

Use this path if you are not on Ubuntu or prefer manual control.

### Prerequisites

| Tool | Install |
|------|---------|
| Docker Desktop | [Mac](https://docs.docker.com/desktop/install/mac-install/) · [Windows](https://docs.docker.com/desktop/install/windows-install/) |
| Conda (Miniconda) | [Mac](https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOS-arm64.sh) · [Windows](https://docs.conda.io/en/latest/miniconda.html) |
| Node.js ≥ 18 | [nodejs.org](https://nodejs.org/) |

### 1. Clone

```bash
git clone --recurse-submodules <repo-url>
cd chrono-rag
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
OPENAI_API_KEY=<your-openai-api-key>
ANTHROPIC_API_KEY=<your-anthropic-api-key>
```

### 3. Start MongoDB

```bash
docker pull mongodb/mongodb-atlas-local
docker run -d --name atlas_local --restart unless-stopped \
  -p 27017:27017 \
  -v atlas_data:/data/db \
  -v atlas_mongot_data:/data/mongot \
  mongodb/mongodb-atlas-local:latest
```

### 4. Install Python dependencies

```bash
conda create -n chrono python=3.12 -y
conda install -n chrono projectchrono::pychrono -c conda-forge -y
conda run -n chrono pip install -r requirements.txt
```

### 5. Start the backend

```bash
conda run -n chrono python -m uvicorn main:app \
  --host 127.0.0.1 --port 8000 --reload --app-dir src
```

### 6. Index the data (first run only)

```bash
curl -s -X POST http://localhost:8000/index
```

### 7. Start the frontend

```bash
cd frontend && npm install && npm run dev
```

The app will be available at **http://localhost:5173**.

---

## Subsequent Runs

```bash
docker start atlas_local   # skip if container auto-restarts

conda run -n chrono python -m uvicorn main:app \
  --host 127.0.0.1 --port 8000 --reload --app-dir src

cd frontend && npm run dev
```

---

## API Reference

### `POST /index`
Parses the repos directory, generates embeddings, and upserts all chunks into MongoDB.

```json
{ "chunks_indexed": 142 }
```

### `POST /search`
Runs a vector search and returns an LLM-generated answer.

**Request**
```json
{ "query": "How do I create a rigid body in PyChrono?", "top_k": 5, "model": "claude-opus-4-8" }
```

**Response**
```json
{ "answer": "To create a rigid body..." }
```

`top_k` defaults to `5`. `model` defaults to `"claude-opus-4-8"` — also accepts `"gpt-4o-mini"`.
