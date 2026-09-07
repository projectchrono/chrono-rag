# chrono-rag

Ask questions about [Project Chrono](https://github.com/projectchrono/chrono) and PyChrono and get
answers grounded in Chrono's own source code, demos, and documentation, with the files cited. It runs
on your machine, needs no account or API key to start, and works from a terminal, from your code
editor, or from a local web page.

How it works, in one sentence: for each question it searches an index of the Chrono codebase, hands
only the matching pieces to an LLM, and has the LLM answer from those; if nothing relevant is found it
says so instead of guessing.

## Install (about 5 minutes)

You need [conda](https://conda-forge.org/download/) (Miniforge is fine) and git.

```bash
git clone https://github.com/projectchrono/chrono-rag.git
cd chrono-rag
./setup.sh              # Windows PowerShell:  .\setup.ps1
```

The script creates a conda env named `chrono-rag`, installs the tool into it, and downloads the
prebuilt search index (about 50 MB). (If PowerShell refuses to run scripts, use
`powershell -ExecutionPolicy Bypass -File .\setup.ps1`.) Then:

```bash
conda activate chrono-rag
chrono-rag search "how do I attach a lidar in pychrono"
```

That is a working code search over Chrono. The very first search downloads a small embedding model
once (about 130 MB, network needed that one time). If anything misbehaves, `chrono-rag doctor` says
what is missing and how to fix it.

**Which Chrono version does it know?** The default index is a snapshot of Chrono's `main` branch,
rebuilt monthly, and every answer states the snapshot date. If you use the PyChrono 10.0.0 release
from conda, switch to the matching index once:

```bash
chrono-rag get-index --channel 10.0.0 --force
```

## Get written answers

`search` shows matching code. `ask` sends those matches to an LLM and prints an answer, the source
files, and which LLM wrote it. Pick one of the two options below; nothing else is needed.

**Option A: a cloud LLM with your own key** (a few cents per question).

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # PowerShell:  $env:ANTHROPIC_API_KEY="sk-ant-..."
chrono-rag ask "create a rigid body box in pychrono" --provider anthropic
```

`--provider openai` with `OPENAI_API_KEY` works the same way.

**Option B: a free local LLM** (no key, offline, less capable than the big cloud models). Run
[AMD Lemonade](https://lemonade-server.ai/) or any OpenAI-compatible server, then tell chrono-rag
where it is:

```bash
export CHRONO_RAG_LLM_PROVIDER=local
export CHRONO_RAG_LLM_BASE_URL=http://localhost:13305/v1
export CHRONO_RAG_LLM_MODEL=Qwen2.5-Coder-32B-Instruct-GGUF
chrono-rag ask "create a rigid body box in pychrono"
```

(PowerShell: `$env:NAME="value"` for each line.) Searching always stays local; only the LLM that
writes the answer differs between the options.

## Use it from your editor (Cursor, Claude Code, VS Code, ...)

Editors that speak MCP can call chrono-rag as a tool while you work. Print the ready-made config
entry, with the absolute paths for your machine filled in:

```bash
chrono-rag mcp-config
```

Paste it into your editor's MCP settings (Cursor: `.cursor/mcp.json`; VS Code: `.vscode/mcp.json`;
Claude Code: `claude mcp add-json chrono-rag '<the chrono-rag object>'`) and restart the editor. The
editor then gets two tools: `search_chrono` (code search) and `chrono_digest` (a short map of Chrono's
modules, from [docs/chrono-digest.md](docs/chrono-digest.md)).

One caveat: in editor mode the editor's own LLM decides whether to search, so an answer is not
guaranteed to have gone through chrono-rag. The terminal and the web app always search first.

## Web app (optional)

A local browser page over the same machinery. Set up an answer LLM as in "Get written answers" (keys
may also live in a `.env` file, see [.env.example](.env.example)), then run the backend and the
frontend in two terminals:

```bash
python -m uvicorn chrono_rag.webapp:app --port 8000        # terminal 1, env activated
cd frontend && npm install && npm run dev                   # terminal 2 (Node 18+)
```

Open http://localhost:5173. Details, including a conda-based Node install, in
[frontend/README.md](frontend/README.md).

## What you can trust in an answer

Retrieval runs before the LLM; the LLM only sees the retrieved code. Every answer lists the source
files used and names the LLM that wrote it, and each result set states the Chrono checkout it came
from (release or dated snapshot). If retrieval finds nothing relevant, the tool says so and does not
call an LLM. Grounding reduces, but does not eliminate, wrong answers: check the cited files.

---

## Advanced

### Index channels and how they stay current

Two prebuilt indexes are published as GitHub Releases and every answer says which one it used:

| channel | built from | for whom |
|---|---|---|
| `main` (default) | Chrono's development branch, dated snapshot, rebuilt monthly | anyone building Chrono from source; covers post-10.0 work such as the AMD ROCm/HIP GPU backend |
| `10.0.0` | the 10.0.0 release tag | users of the conda PyChrono 10.0.0 package |

`.github/workflows/index-release.yml` rebuilds `main` on the first of every month, gates on the
retrieval eval, and publishes `index-main-YYYY-MM-DD` with assets `chrono-rag-index-main-<date>-<sha>.zip`
(+ `.sha256`); `chrono-rag get-index` takes the newest release of the requested channel. Any Chrono
tag can be indexed by running that workflow by hand with the tag as `chrono_ref` ("Run workflow" in
the Actions tab); its assets are `chrono-rag-index-<tag>-<sha>.zip`. GitHub pauses scheduled workflows
on repositories with no activity for 60 days; re-enable from the Actions tab if the monthly build stops.

### Build your own index

```bash
CHRONO_RAG_REPO=/path/to/chrono python -m chrono_rag.preprocess.build_index
```

Only git-tracked files are indexed. The checked-out ref decides the scope label: a release tag gives
"PyChrono 10.0", anything else a dated development-snapshot label (override with `CHRONO_RAG_REF`).

### Optional: forum search

A second index built from curated PyChrono examples and the public
[ProjectChrono Google Group](https://groups.google.com/g/projectchrono): questions people have
actually asked and had answered. Posts before 2020 and install/build threads are dropped, and personal
information (email addresses, author and greeting names) is stripped before indexing; see
[DATA.md](DATA.md).

```bash
chrono-rag get-index --forum
CHRONO_RAG_EXTRA_INDEX=index-forum chrono-rag search "attach a lidar sensor"     # PowerShell: $env:CHRONO_RAG_EXTRA_INDEX="index-forum"
```

Forum results rank slightly below code and docs. Several extra indexes are separated with the OS path
separator (`;` on Windows, `:` elsewhere). To rebuild it from a fresh Google Takeout export of the
group (never committed; it contains real names before curation):

```bash
python -m chrono_rag.preprocess.build_examples_index                       # sibling pychrono-examples-10.0 checkout
python -m chrono_rag.preprocess.build_forum_index path/to/topics.mbox index-forum
```

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
| `CHRONO_RAG_REF` | git ref of that clone, for the scope label (index build only) | detected via git |
| `CHRONO_RAG_EMBED_MODEL` | embedding model (index build only) | `BAAI/bge-small-en-v1.5` |
| `CHRONO_RAG_VERSION` | Chrono version number override (index build only) | parsed from the checkout |
| `CHRONO_RAG_ENV` | conda env name used by the setup scripts | `chrono-rag` |

### Developing

```bash
pytest                                        # unit tests
python -m chrono_rag.eval.run_eval            # retrieval quality check against the loaded index
```

The setup script is equivalent to `conda create -n chrono-rag python=3.12` followed by
`pip install -e ".[llm,web,mcp,dev]"` inside that env. See [CONTRIBUTING.md](CONTRIBUTING.md).
Licensing and attribution: [LICENSE](LICENSE) and [NOTICE](NOTICE); data provenance and privacy:
[DATA.md](DATA.md); security and removal reports: [SECURITY.md](SECURITY.md).
