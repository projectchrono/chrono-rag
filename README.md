# chrono-rag

A retrieval-based question-answering tool for [Project Chrono](https://github.com/projectchrono/chrono)
and PyChrono 10.0. It answers questions using Chrono's own source code, demos, and documentation, and
cites the files it used.

For each question it retrieves the relevant parts of the current Chrono codebase, passes only those to an
LLM, and has the LLM answer from them. If it finds nothing relevant, it reports that instead of answering.
Keeping answers tied to the actual code reduces, though does not eliminate, the incorrect or
version-mismatched answers a general chatbot can give.

It runs locally and needs no account or API key to start. The answer step can use a local LLM or a cloud
LLM, selectable per query. It can be used from a terminal, a code editor (via MCP), or a local web app.

> Scope: PyChrono 10.0. Older versions are not covered.

## Quickstart (no API key needed)

Requires [conda](https://conda-forge.org/). From a clone of this repository:

```bash
./setup.sh                                        # Windows PowerShell: .\setup.ps1
conda run -n chrono-rag chrono-rag get-index      # downloads the prebuilt search index
conda run -n chrono-rag chrono-rag search "how do I attach a lidar in pychrono"
```

That is a working code search over the Chrono codebase. The first search downloads a small embedding
model once (needs network that one time). `conda activate chrono-rag` lets you drop the `conda run`
prefix. If anything misbehaves, `chrono-rag doctor` reports what is missing.

The setup script does two things you can also do by hand: create the env
(`conda create -n chrono-rag python=3.12`) and install this package into it
(`pip install -e ".[llm,web,mcp,dev]"`).

## Ways to use it

1. **Terminal** - `chrono-rag search` (retrieval only) and `chrono-rag ask` (written answer).
2. **Editor** (Cursor, Claude Code, VS Code, ...) via MCP - ask while working in code.
3. **Local web app** - a browser interface.

## Terminal: ask for written answers

`search` needs no key. `ask` passes the retrieved code to an LLM and prints the answer, the source files
used, and the LLM that produced it:

```bash
chrono-rag ask "create a rigid body box in pychrono"
```

This needs an answer LLM, local or cloud (see the next section). Set the options as environment
variables (PowerShell: `$env:NAME="value"`; macOS/Linux: `export NAME=value`).

**Local LLM.** Run an LLM locally with [AMD Lemonade](https://lemonade-server.ai/) (or any
OpenAI-compatible local server) and point chrono-rag at it: no key, no per-query cost, works offline.
Local LLMs are generally less capable than large cloud LLMs.

```
CHRONO_RAG_LLM_PROVIDER = local
CHRONO_RAG_LLM_BASE_URL = http://localhost:13305/v1          # your local server's address
CHRONO_RAG_LLM_MODEL    = Qwen2.5-Coder-32B-Instruct-GGUF
```

**Cloud LLM.** Provide your own API key, then add `--provider`:

```
ANTHROPIC_API_KEY = sk-ant-...        # your key; roughly a few cents per question
# then: chrono-rag ask "..." --provider anthropic     (or --provider openai with OPENAI_API_KEY)
```

In both cases search runs locally; only the LLM that writes the answer differs.

## Use it in your editor

If your editor supports MCP (Cursor, Claude Code, Windsurf, ...), add this to its MCP settings (for
example `.cursor/mcp.json`, or Claude Code's config). The `chrono-rag-mcp` command is installed into the
conda env by the setup above (`Scripts/` on Windows, `bin/` on macOS/Linux):

```json
{
  "mcpServers": {
    "chrono-rag": {
      "command": "<path-to>/.conda/envs/chrono-rag/Scripts/chrono-rag-mcp"
    }
  }
}
```

If your index is not at the repo default, add `"env": { "CHRONO_RAG_INDEX": "<path>" }`. The server
exposes two tools: `search_chrono` (code search) and `chrono_digest` (a curated architecture map of
Chrono, from [docs/chrono-digest.md](docs/chrono-digest.md)).

## What each answer includes

On the terminal and web app, retrieval always runs before the LLM: the LLM receives only the retrieved
context, the printed answer lists the source files, and it names the LLM used. If retrieval finds nothing
relevant, the tool reports that and does not call an LLM.

In editor/MCP mode the editor's own LLM decides whether to call the search tool, so retrieval is not
guaranteed and the answer is not produced by this tool's pipeline. Use the terminal or web app for the
guaranteed retrieve-then-answer behavior.

## Web app

Backend (needs the `[web]` extra and an answer LLM; keys can live in a `.env`, see
[.env.example](.env.example)):

```bash
conda run -n chrono-rag python -m uvicorn chrono_rag.webapp:app --port 8000
```

Frontend (Node 18+; on a conda machine `conda create -n chrono-rag-node -c conda-forge "nodejs>=20"`):

```bash
cd frontend && npm install && npm run dev     # then open http://localhost:5173
```

The page shows the answer, the source files used, the answering LLM, and a clear notice when retrieval
found nothing relevant. Details in [frontend/README.md](frontend/README.md).

---

## How it works

chrono-rag reads a copy of the Chrono code, splits it into units (functions, classes, doc sections), and
converts each unit into a vector ("fingerprint") with a small local embedding model. A query is matched
against those vectors, combined with a keyword search and an exact name match, to select the most relevant
units. If nothing relevant is found, it reports that instead of answering. Python/PyChrono code is
weighted higher for Python queries. The output is a small `index/` folder that stays on your machine. Two
models are involved: the embedding model selects the relevant code, and the LLM writes the answer.

### Build your own index

Instead of downloading the prepared one, build it from a Chrono checkout:

```bash
CHRONO_RAG_REPO=/path/to/chrono conda run -n chrono-rag python -m chrono_rag.preprocess.build_index
```

### Optional: forum search

There's a second, optional index built from ProjectChrono examples and the
[ProjectChrono Google Group](https://groups.google.com/g/projectchrono) forum, covering
questions people have actually asked (and answered) about PyChrono 10.0. It's curated to stay
current: posts older than 2020 and install/build/compile threads are dropped, and personal
information (email addresses, and author and greeting names) is stripped before indexing; see
[DATA.md](DATA.md) for the full provenance and privacy notes.

To turn it on:

```bash
conda run -n chrono-rag chrono-rag get-index --forum
# then point chrono-rag at it:
CHRONO_RAG_EXTRA_INDEX=index-forum chrono-rag search "attach a lidar sensor"
```

Forum results are ranked slightly below code/docs, so they only show up first when they're
clearly the best match.

**Refreshing the forum export.** The source data (`topics.mbox`) is a
[Google Takeout](https://takeout.google.com/) export of the ProjectChrono Google Group, taken
from an account subscribed to the group. It is never committed (before curation it contains real
names and email addresses). To rebuild `index-forum/` from a fresh export, run from the repo root:

```bash
# 1. Build the examples index (defaults to a sibling pychrono-examples-10.0 checkout):
conda run -n chrono-rag python -m chrono_rag.preprocess.build_examples_index
# 2. Append the curated, PII-scrubbed forum posts into the same index-forum/ folder:
conda run -n chrono-rag python -m chrono_rag.preprocess.build_forum_index path/to/topics.mbox index-forum
```

On Windows, separate multiple `CHRONO_RAG_EXTRA_INDEX` paths with `;` (the OS path separator),
not `:`.

### Settings (environment variables)

| Variable | What it does | Default |
|---|---|---|
| `CHRONO_RAG_INDEX` | where the index folder lives | `<repo>/index` |
| `CHRONO_RAG_EXTRA_INDEX` | optional supplemental index(es), `os.pathsep`-separated | - |
| `CHRONO_RAG_LLM_PROVIDER` | which backend writes answers: `anthropic` / `openai` / `local` | auto |
| `CHRONO_RAG_LLM_BASE_URL` | address of a local / compatible server | - |
| `CHRONO_RAG_LLM_MODEL` | which LLM to use | provider default |
| `CHRONO_RAG_LLM_API_KEY` | API key (a dummy is fine for `local`) | from your environment |
| `CHRONO_RAG_DIGEST` | architecture-overview file for `chrono_digest` | `docs/chrono-digest.md` |
| `CHRONO_RAG_REPO` | your Chrono clone (index build only) | required for builds |
| `CHRONO_RAG_EMBED_MODEL` | embedding model (index build only) | `BAAI/bge-small-en-v1.5` |
| `CHRONO_RAG_VERSION` | version label override (index build only) | parsed from the checkout |
| `CHRONO_RAG_ENV` | conda env name used by the setup scripts | `chrono-rag` |

### Developing

```bash
conda run -n chrono-rag pytest                                   # unit tests
conda run -n chrono-rag python -m chrono_rag.eval.run_eval       # retrieval quality check
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensing and attribution: [LICENSE](LICENSE) and
[NOTICE](NOTICE); data provenance and privacy: [DATA.md](DATA.md); security and removal
reports: [SECURITY.md](SECURITY.md).
