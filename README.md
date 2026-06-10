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
{ "query": "How do I create a rigid body in PyChrono?", "top_k": 5 }
```

**Response**
```json
{ "answer": "To create a rigid body..." }
```

`top_k` is optional (default: 5).

## Running

**Backend**
```bash
cd src && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend**
```bash
cd frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Setup Notes

- Set `REPOS_DIR` in `.env` to point at your local clone of the Chrono/PyChrono repos.
- Run `POST /index` once to populate the vector store before searching.
- Requires MongoDB with Atlas Vector Search enabled and an OpenAI API key.
