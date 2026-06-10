# Chrono RAG — Frontend

A dark-themed search interface for the Chrono RAG backend. Ask questions about Chrono and PyChrono and get LLM-generated answers backed by vector search.

## Requirements

- Node.js 18+
- The [Chrono RAG backend](../src/README.md) running at `http://localhost:8000`

## Installation

```bash
cd frontend
npm install
```

## Development

Start the dev server (proxies `/search` to the backend automatically):

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

The backend must be running for search to work:

```bash
# From the repo root
cd src && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## Testing

```bash
npm test          # run once
npm run test:watch  # watch mode
```

19 tests across `SearchBar`, `AnswerCard`, and `App`.

## Build

```bash
npm run build     # outputs to frontend/dist/
npm run preview   # preview the production build locally
```

## Project Structure

```
src/
  App.jsx              # root component — owns all state, handles fetch
  App.module.css
  components/
    SearchBar.jsx      # controlled input + submit button
    SearchBar.module.css
    AnswerCard.jsx     # renders loading / error / markdown answer
    AnswerCard.module.css
```
