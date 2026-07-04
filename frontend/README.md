# Chrono RAG - Frontend

A dark-themed search interface for the chrono-rag backend. Ask questions about Chrono and
PyChrono; answers come with the source files used and the LLM that produced them.

## Requirements

1. Node.js 18+ (on a conda machine: `conda create -n chrono-rag-node -c conda-forge "nodejs>=20"`).
2. The chrono-rag backend running at `http://localhost:8000` (see below).

## Run it

Terminal 1, the backend (from the repo root; needs the `[web]` extra and an answer LLM, see the
root [README](../README.md)):

```bash
python -m uvicorn chrono_rag.webapp:app --port 8000
```

Terminal 2, the frontend dev server (proxies `/search` to the backend):

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

The model toggle selects the answer LLM: a cloud model (the server needs `ANTHROPIC_API_KEY` /
`OPENAI_API_KEY`, e.g. via a `.env` file, see `.env.example` at the repo root) or "Local LLM"
(the server needs `CHRONO_RAG_LLM_BASE_URL` pointing at an OpenAI-compatible local server).

## Testing

```bash
npm test            # run once
npm run test:watch  # watch mode
```

## Build

```bash
npm run build     # outputs to frontend/dist/
npm run preview   # preview the production build locally
```

## Project structure

```
src/
  App.jsx              # root component - owns all state, handles fetch
  components/
    SearchBar.jsx      # controlled input + submit button + model toggle
    AnswerCard.jsx     # loading / error / abstention notice / answer +
                       # sources + answered-by footer
```
