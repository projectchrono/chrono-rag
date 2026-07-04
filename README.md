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

## Ways to use it

1. **Terminal** - type a question, get an answer.
2. **Editor** (Cursor, Claude Code, VS Code, ...) via MCP - ask while working in code.
3. **Local web app** - a browser interface.

## Get started (terminal)

Requires [conda](https://conda-forge.org/).

```bash
# 1. Create an environment and install the dependencies
conda create -n chrono-rag python=3.12 -y
conda run -n chrono-rag pip install -r requirements.txt
```

**2. Get the search index.** A prepared snapshot of Chrono's code used for search. Download it from the
[Releases page](https://github.com/uwsbel/chrono-rag/releases) (the `chrono-rag-index-*.zip` file) and
unzip it so you have an `index/` folder here. Building your own is described below.

**3. Run a query.**

```bash
# Find the relevant code (no LLM, nothing else to set up):
conda run -n chrono-rag python src/surfaces/cli.py search "how do I attach a lidar in pychrono"

# Get a written answer (needs an LLM; see "Answer LLM" below):
conda run -n chrono-rag python src/surfaces/cli.py ask "create a rigid body box in pychrono"
```

`search` lists the matching code with file names and line numbers. `ask` passes that code to an LLM and
prints the answer, the source files used, and the LLM that produced it.

## Use it in your editor

If your editor supports MCP (Cursor, Claude Code, Windsurf, ...), add this to its MCP settings (for
example `.cursor/mcp.json`, or Claude Code's config):

```json
{
  "mcpServers": {
    "chrono-rag": {
      "command": "<path-to>/.conda/envs/chrono-rag/python.exe",
      "args": ["<repo>/src/surfaces/mcp_server.py"],
      "env": { "CHRONO_RAG_INDEX": "<path-to-your-index-folder>" }
    }
  }
}
```

The first query downloads a small embedding model (a one-time download), so it needs network access once.

## What each answer includes

On the terminal and web app, retrieval always runs before the LLM: the LLM receives only the retrieved
context, the printed answer lists the source files, and it names the LLM used. If retrieval finds nothing
relevant, the tool reports that and does not call an LLM.

In editor/MCP mode the editor's own LLM decides whether to call the search tool, so retrieval is not
guaranteed and the answer is not produced by this tool's pipeline. Use the terminal or web app for the
guaranteed retrieve-then-answer behavior.

## Answer LLM (local or cloud)

Search runs locally and needs no key. Producing a written answer needs an LLM, which you select. Set the
options below as environment variables (PowerShell: `$env:NAME="value"`; macOS/Linux: `export NAME=value`).

**Local LLM.** Run an LLM locally with [AMD Lemonade](https://lemonade-server.ai/) (or any
OpenAI-compatible local server) and point chrono-rag at it: no key, no per-query cost, works offline.
Local LLMs are generally less capable than large cloud LLMs.

```
CHRONO_RAG_LLM_PROVIDER = local
CHRONO_RAG_LLM_BASE_URL = http://localhost:13305/api/v1      # your local server's address
CHRONO_RAG_LLM_MODEL    = Qwen2.5-Coder-32B-Instruct-GGUF
```

**Cloud LLM.** Provide your own API key, then add `--provider`:

```
ANTHROPIC_API_KEY = sk-ant-...        # your key; roughly a few cents per question
# then: ... cli.py ask "..." --provider anthropic     (or --provider openai with OPENAI_API_KEY)
```

In both cases search runs locally; only the LLM that writes the answer differs.

## Web app

```bash
conda run -n chrono-rag python -m uvicorn main:app --app-dir src --port 8000
cd frontend && npm install && npm run dev
```

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
# set CHRONO_RAG_REPO to your Chrono clone, then:
conda run -n chrono-rag python src/preprocess/build_index.py
```

### Optional: forum search

There's a second, optional index built from ProjectChrono examples and the
[ProjectChrono Google Group](https://groups.google.com/g/projectchrono) forum, covering
questions people have actually asked (and answered) about PyChrono 10.0. It's curated to stay
current: posts older than 2020 and install/build/compile threads are dropped, and personal
information (email addresses, and author and greeting names) is stripped before indexing.

To turn it on, download the `chrono-rag-index-forum-*.zip` file from the
[Releases page](https://github.com/uwsbel/chrono-rag/releases), unzip it so you have an
`index-forum/` folder here, and point chrono-rag at it:

```bash
CHRONO_RAG_EXTRA_INDEX=index-forum conda run -n chrono-rag \
    python src/surfaces/cli.py search "attach a lidar sensor"
```

Forum results are ranked slightly below code/docs, so they only show up first when they're
clearly the best match.

**Refreshing the forum export.** The source data (`topics.mbox`) is a
[Google Takeout](https://takeout.google.com/) export of the ProjectChrono Google Group, taken
from an account subscribed to the group. It is never committed (before curation it contains real
names and email addresses). To rebuild `index-forum/` from a fresh export, run from the repo root:

```bash
# 1. Build the examples index (defaults to a sibling pychrono-examples-10.0 checkout):
conda run -n chrono-rag python src/preprocess/build_examples_index.py
# 2. Append the curated, PII-scrubbed forum posts into the same index-forum/ folder:
conda run -n chrono-rag python src/preprocess/build_forum_index.py path/to/topics.mbox index-forum
```

On Windows, separate multiple `CHRONO_RAG_EXTRA_INDEX` paths with `;` (the OS path separator),
not `:`.

### Settings (environment variables)

| Variable | What it does | Default |
|---|---|---|
| `CHRONO_RAG_INDEX` | where the index folder lives | `<repo>/index` |
| `CHRONO_RAG_LLM_PROVIDER` | which backend writes answers: `anthropic` / `openai` / `local` | auto |
| `CHRONO_RAG_LLM_BASE_URL` | address of a local / compatible server | - |
| `CHRONO_RAG_LLM_MODEL` | which LLM to use | provider default |
| `CHRONO_RAG_LLM_API_KEY` | API key (a dummy is fine for `local`) | from your environment |
| `CHRONO_RAG_REPO` | your Chrono clone (only when building an index) | - |
| `CHRONO_RAG_DIGEST` | optional architecture-overview file | `docs/chrono-digest.md` |

### Developing

```bash
conda run -n chrono-rag python src/eval/run_eval.py    # retrieval quality check
conda run -n chrono-rag pytest                          # unit tests
```
