# chrono-rag

A friendly helper for [Project Chrono](https://github.com/projectchrono/chrono) and **PyChrono 10.0**.
Ask a question in plain English, like *"how do I attach a lidar sensor?"*, and it finds the answer in
Chrono's own source code, demos, and docs, and points you at the exact files.

It runs on your own computer. No accounts, no database to install, and no paid key needed to get started.

> It focuses on **PyChrono 10.0**. Older versions aren't covered yet.

## Three ways to use it

Pick whatever fits how you work:

1. **In your terminal** - type a question, get an answer.
2. **In your editor** (Cursor, Claude Code, VS Code, ...) - ask while you code, and it pulls the
   relevant Chrono code in for you.
3. **In a local web page** - a simple browser app, if you prefer clicking to typing.

## Get started (terminal)

You'll need [conda](https://conda-forge.org/). Three short steps:

```bash
# 1. Create an environment and install the dependencies
conda create -n chrono-rag python=3.12 -y
conda run -n chrono-rag pip install -r requirements.txt
```

**2. Get the search index.** This is a prepared snapshot of Chrono's code that makes searching fast.
Download the ready-made one from the [Releases page](https://github.com/uwsbel/chrono-rag/releases)
(the `chrono-rag-index-*.zip` file) and unzip it so you have an `index/` folder here. That's the easy
path; building your own is covered near the bottom.

**3. Ask away.**

```bash
# Find the relevant code (instant, nothing else to set up):
conda run -n chrono-rag python src/surfaces/cli.py search "how do I attach a lidar in pychrono"

# Get a written answer (needs an answer model; see "Free or best answers" below):
conda run -n chrono-rag python src/surfaces/cli.py ask "create a rigid body box in pychrono"
```

`search` lists the matching code with file names and line numbers. `ask` reads that code and writes you
an answer, along with the files it used.

## Use it in your editor

If your editor supports MCP (Cursor, Claude Code, Windsurf, ...), you can ask Chrono questions right
where you code. Add this to your editor's MCP settings (for example `.cursor/mcp.json`, or Claude Code's
config):

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

The very first question downloads a small search model (a one-time download), so it needs internet once.

## Free or best answers

Searching for code is always free and works offline. Writing an answer needs a language model, and you
choose which one. Set the options below as environment variables
(PowerShell: `$env:NAME="value"`; macOS/Linux: `export NAME=value`).

**Free, on your machine.** Run a model locally with [AMD Lemonade](https://lemonade-server.ai/) (or any
compatible local server) and point chrono-rag at it. No key, no cost, works offline. Local models are
good, just not as sharp as the big cloud ones.

```
CHRONO_RAG_LLM_PROVIDER = local
CHRONO_RAG_LLM_BASE_URL = http://localhost:13305/api/v1      # your local server's address
CHRONO_RAG_LLM_MODEL    = Qwen2.5-Coder-32B-Instruct-GGUF
```

**Best quality (paid).** Use a top cloud model by providing your own API key, then add `--provider`:

```
ANTHROPIC_API_KEY = sk-ant-...        # your key; roughly a few cents per question
# then: ... cli.py ask "..." --provider anthropic     (or --provider openai with OPENAI_API_KEY)
```

Either way, the part that searches Chrono always runs locally; only the model that writes the answer
changes.

## Web app (optional)

Prefer a browser? Run the local web app:

```bash
conda run -n chrono-rag python -m uvicorn main:app --app-dir src --port 8000
cd frontend && npm install && npm run dev
```

---

## Under the hood (for the curious)

You don't need any of this to use it.

chrono-rag reads a copy of the Chrono code, splits it into meaningful pieces (functions, classes, doc
sections), and turns each piece into a numeric "fingerprint" using a small model that runs locally. Your
question is matched against those fingerprints, combined with a plain keyword search and an exact
name match, to surface the most relevant pieces. If nothing relevant comes up, it says so instead of
guessing. Python/PyChrono code is favored for Python questions. The result is a small `index/` folder
that stays entirely on your machine.

### Build your own index

Instead of downloading the prepared one, build it from a Chrono checkout:

```bash
# set CHRONO_RAG_REPO to your Chrono clone, then:
conda run -n chrono-rag python src/preprocess/build_index.py
```

### Settings (environment variables)

| Variable | What it does | Default |
|---|---|---|
| `CHRONO_RAG_INDEX` | where the index folder lives | `<repo>/index` |
| `CHRONO_RAG_LLM_PROVIDER` | who writes answers: `anthropic` / `openai` / `local` | auto |
| `CHRONO_RAG_LLM_BASE_URL` | address of a local / compatible server | - |
| `CHRONO_RAG_LLM_MODEL` | which model to use | provider default |
| `CHRONO_RAG_LLM_API_KEY` | API key (a dummy is fine for `local`) | from your environment |
| `CHRONO_RAG_REPO` | your Chrono clone (only when building an index) | - |
| `CHRONO_RAG_DIGEST` | optional architecture-overview file | `docs/chrono-digest.md` |

### Developing

```bash
conda run -n chrono-rag python src/eval/run_eval.py    # retrieval quality check
conda run -n chrono-rag pytest                          # unit tests
```
