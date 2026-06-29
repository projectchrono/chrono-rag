# chrono-rag

A local, code-aware retrieval assistant for [Chrono](https://github.com/projectchrono/chrono)
and **PyChrono 10.0**. Ask how to do something in PyChrono and get the relevant source,
demos, and API back, inside your AI editor, from a terminal, or a local web page.

No Docker, no database server. Default mode is fully local: a small ONNX embedding model plus
an in-memory hybrid (dense + BM25 + symbol) index over the Chrono codebase. An optional
OpenAI-backed index (converted from a MongoDB dump) can be swapped in with one env var.

> Scope: answers target **PyChrono 10.0**. Older releases are out of scope for now.

## Surfaces

1. **MCP server** - point Cursor, Claude Code, Windsurf, or any MCP editor at it; exposes
   `search_chrono` and `chrono_digest` tools.
2. **CLI** - `search` (raw chunks, no key) and `ask` (LLM answer, bring your own key).
3. **Web** - a local FastAPI app + React UI (bring your own key).

## Quick start

```bash
# 1. Environment (conda-forge)
conda create -n chrono-rag python=3.12 -y
conda run -n chrono-rag pip install -r requirements.txt

# 2. Get an index. Either point at an existing one:
#    set CHRONO_RAG_INDEX=...   (Windows: $env:CHRONO_RAG_INDEX="...")
#    or build one from a Chrono checkout:
conda run -n chrono-rag python src/preprocess/build_index.py   # set CHRONO_RAG_REPO to your clone

# 3a. CLI (no API key needed)
conda run -n chrono-rag python src/surfaces/cli.py search "how do I attach a lidar in pychrono"

# 3b. CLI answer (needs ANTHROPIC_API_KEY or OPENAI_API_KEY)
conda run -n chrono-rag python src/surfaces/cli.py ask "create a rigid body box in pychrono"
```

## Using the OpenAI-backed index (optional)

The main branch stored embeddings in MongoDB (OpenAI `text-embedding-3-small`, 1536-dim).
A one-off conversion script turns that BSON dump into v2's NumPy format so it can be swapped
in with a single env var — no architectural changes.

```bash
# 1. Install pymongo (one-time; only needed for the conversion step)
pip install pymongo

# 2. Convert the BSON dump (accepts a zip or an extracted .bson file)
python scripts/convert_mongo_index.py --zip chrono_embeddings.zip --out index-mongo/

# 3. Use the OpenAI-backed index (needs OPENAI_API_KEY at query time)
CHRONO_RAG_INDEX=./index-mongo python src/surfaces/cli.py search "ChBodyEasyBox"

# Default fastembed index — no change, no API key required
python src/surfaces/cli.py search "ChBodyEasyBox"
```

The retrieval core detects which embedder to use from `manifest.json` inside the index
directory; no code change is needed when switching indexes.

## Use it in your editor (MCP)

Add this to your editor's MCP config (`.cursor/mcp.json`, or Claude Code's `mcpServers`):

```json
{
  "mcpServers": {
    "chrono-rag": {
      "command": "<path-to>/.conda/envs/chrono-rag/python.exe",
      "args": ["<repo>/src/surfaces/mcp_server.py"],
      "env": {
        "CHRONO_RAG_INDEX": "<path-to-index-dir>",
        "CHRONO_RAG_DIGEST": "<path-to-digest.md>",
        "HF_HUB_OFFLINE": "1"
      }
    }
  }
}
```

## Web app

```bash
conda run -n chrono-rag python -m uvicorn main:app --app-dir src --port 8000
cd frontend && npm install && npm run dev
```

## How it works

```
Chrono checkout
  -> structural chunking (AST for Python, tree-sitter for C++)
  -> local ONNX embeddings (fastembed)
  -> index artifact (embeddings.npy + meta.jsonl + manifest.json)
  -> retrieval core: hybrid (dense + BM25 + symbol) + abstention + injection filter
  -> surfaces: MCP / CLI / web
```

Retrieval is PyChrono-first: Python/PyChrono chunks are boosted for Python-phrased queries.

## Configuration (env vars)

| Var | Meaning | Default |
|-----|---------|---------|
| `CHRONO_RAG_INDEX` | index directory | `<repo>/index` |
| `CHRONO_RAG_DIGEST` | architecture digest file | `<repo>/docs/chrono-digest.md` |
| `CHRONO_RAG_REPO` | Chrono checkout (build only) | - |
| `CHRONO_RAG_EMBED_MODEL` | embedder (build only) | `BAAI/bge-small-en-v1.5` |
| `OPENAI_API_KEY` | required when using an OpenAI-backed index | - |

## Development

```bash
conda run -n chrono-rag python src/eval/run_eval.py    # retrieval eval + abstention calibration
conda run -n chrono-rag pytest                          # unit tests
```
