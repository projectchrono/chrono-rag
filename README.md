# chrono-rag

A local, code-aware retrieval assistant for [Chrono](https://github.com/projectchrono/chrono)
and **PyChrono 10.0**. Ask how to do something in PyChrono and get the relevant source,
demos, and API back, inside your AI editor, from a terminal, or a local web page.

No Docker, no database server, no embedding API key. Everything runs locally: a small ONNX
embedding model plus an in-memory hybrid (dense + BM25 + symbol) index over the Chrono codebase.

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

# 2. Get an index. Recommended: download the prebuilt one from the repo's Releases
#    page and unzip it so there is an `index/` folder at the repo root:
#      https://github.com/uwsbel/chrono-rag/releases  ->  chrono-rag-index-<commit>.zip
#    (or point CHRONO_RAG_INDEX at wherever you unzipped it).
#    Advanced: build your own from a Chrono checkout (set CHRONO_RAG_REPO to your clone):
conda run -n chrono-rag python src/preprocess/build_index.py

# 3a. CLI (no API key needed)
conda run -n chrono-rag python src/surfaces/cli.py search "how do I attach a lidar in pychrono"

# 3b. CLI answer, cloud (set ANTHROPIC_API_KEY or OPENAI_API_KEY)
conda run -n chrono-rag python src/surfaces/cli.py ask "create a rigid body box in pychrono"

# 3c. CLI answer, free + local (no key) via an OpenAI-compatible server, e.g. Lemonade
$env:CHRONO_RAG_LLM_PROVIDER="local"; $env:CHRONO_RAG_LLM_BASE_URL="http://localhost:13305/api/v1"
conda run -n chrono-rag python src/surfaces/cli.py ask "create a rigid body box in pychrono"
```

## Use it in your editor (MCP)

Add this to your editor's MCP config (`.cursor/mcp.json`, or Claude Code's `mcpServers`):

```json
{
  "mcpServers": {
    "chrono-rag": {
      "command": "<path-to>/.conda/envs/chrono-rag/python.exe",
      "args": ["<repo>/src/surfaces/mcp_server.py"],
      "env": {
        "CHRONO_RAG_INDEX": "<path-to-index-dir>"
      }
    }
  }
}
```

On first run chrono-rag downloads the small ONNX embedding model (`bge-small`, tens of MB), so the
first query needs network. `CHRONO_RAG_DIGEST` is optional (it enables the `chrono_digest` tool); add
`"HF_HUB_OFFLINE": "1"` to the env only after the embedder is cached, to force fully-offline runs.

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
| `CHRONO_RAG_LLM_PROVIDER` | answer backend: `anthropic` / `openai` / `local` | auto |
| `CHRONO_RAG_LLM_BASE_URL` | OpenAI-compatible URL for `local` | - |
| `CHRONO_RAG_LLM_MODEL` | model id | provider default |
| `CHRONO_RAG_LLM_API_KEY` | key (dummy ok for `local`) | provider env key |

## Answer backend (cloud or local)

The `ask` / web answer path is backend-agnostic (the `anthropic` / `openai` SDKs ship in
`requirements.txt`). Retrieval and embeddings are always local; only the final answer's LLM is your
choice. With nothing configured the provider auto-resolves from your environment.

- **Cloud (recommended for quality):** set `ANTHROPIC_API_KEY` (default `claude-opus-4-8`) or
  `OPENAI_API_KEY` (`--model gpt-4o-mini`), then run `ask --provider anthropic`. Runs the full
  pipeline (retrieval + grounding + refuse + deterministic citations) on a frontier model. The key is
  separate from any Claude Code subscription; personal-use cost is a few cents per query.
- **Local, free, no key (AMD Lemonade or any OpenAI-compatible server):** install Lemonade (see its
  docs), pull a coding model (`Qwen2.5-Coder-32B-Instruct-GGUF` on the GPU; a `-Hybrid` model runs on
  a Ryzen AI NPU), then point chrono-rag at it. The C++ installer serves at
  `http://localhost:13305/api/v1`; the pip `lemonade-sdk` dev server at `http://localhost:8000/api/v1`.

  ```bash
  $env:CHRONO_RAG_LLM_PROVIDER="local"
  $env:CHRONO_RAG_LLM_BASE_URL="http://localhost:13305/api/v1"
  $env:CHRONO_RAG_LLM_MODEL="Qwen2.5-Coder-32B-Instruct-GGUF"
  conda run -n chrono-rag python src/surfaces/cli.py ask "create a rigid body box in pychrono"
  ```

  Local models are weaker at PyChrono code than the cloud models; the trade is
  free, offline, and private.

## Development

```bash
conda run -n chrono-rag python src/eval/run_eval.py    # retrieval eval + abstention calibration
conda run -n chrono-rag pytest                          # unit tests
```
