# Changelog

## 1.0.0 (2026-09)

First release from the official home, `projectchrono/chrono-rag` (moved from `uwsbel`).

- MCP: works with both MCP Python SDK majors. 2.x renamed `FastMCP` to `MCPServer` and removed
  `mcp.server.fastmcp` (PR #5, @jamesh4470); the server now imports `MCPServer` and falls back to
  `FastMCP`, so existing 1.x installs keep working. CI exercises both.
- Index channels: `chrono-rag get-index --channel main|10.0.0`. `main` (default) is a dated
  snapshot of Chrono's development branch and covers post-10.0 work (AMD ROCm/HIP GPU backend,
  Vulkan/Metal sensor backends, FEA multiphysics, preCICE, FSI-SPH API changes, SCM GPU terrain);
  `10.0.0` matches the conda PyChrono release. The manifest records `channel`, `chrono_ref`,
  `built_at`, and the scope label printed with every answer now names a snapshot by date.
- Monthly index refresh: the publish workflow runs on a schedule, gates on the retrieval eval,
  skips when Chrono's commit is already published, and creates the release itself
  (`index-main-YYYY-MM-DD`). Release-asset names are the contract with `get-index`. The embedding
  is sharded across 8 parallel jobs (`CHRONO_RAG_SHARD=i/N`, merged by `merge_shards`), because one
  GitHub-hosted runner did not finish the corpus in 5 hours.
- Index builder: indexes only git-tracked files (a local build tree in the checkout used to leak in).
- Eval: gold entries can be channel-specific; six entries added for post-10.0 content.
- Digest (`chrono_digest`): refreshed for current main, with main-only items marked.
- Onboarding: the setup scripts now also download the index; new `chrono-rag mcp-config` prints the
  editor (MCP) config entry with absolute paths; README restructured install-first, advanced material last.
- Repository: the 51 MB legacy `chrono_embeddings.zip` was removed from history and stale
  branches deleted, so a clone is a few MB.

## 0.9.0 (2026-07)

Preparation release for the move to an official home.

- Packaging: the code is now a proper installable package (`pip install -e .` in a conda
  env), with console commands `chrono-rag` (search / ask / get-index / doctor) and
  `chrono-rag-mcp`, and optional extras `[llm]`, `[web]`, `[mcp]`.
- New `chrono-rag get-index` downloads and sha256-verifies the prebuilt index;
  `chrono-rag doctor` self-checks the local setup.
- MCP: fixed a first-run failure (offline mode was forced before the embedding model could
  ever download); the `chrono_digest` tool now ships its digest (`docs/chrono-digest.md`).
- Web app: shows the sources used, the answering LLM, and the abstention notice; surfaces
  real error messages; adds a local-LLM option; plain-HTTP dev server.
- CLI: clean, actionable messages for a missing index or a failed/unauthorized LLM call.
- Index builders: `CHRONO_RAG_REPO` is required with clear errors; examples now live only in
  the optional supplemental index (no more double counting); the version label follows the
  index manifest.
- Governance: NOTICE (Project Chrono attribution), DATA.md (forum provenance, PII scrubbing,
  removal contact), SECURITY.md, CONTRIBUTING.md.
- Tests: 21 Python (incl. the forum PII scrubber) + 23 frontend.

## Earlier

- 2026-07: optional forum + examples supplemental index (PR #4), enabled via
  `CHRONO_RAG_EXTRA_INDEX`; published as its own release asset.
- 2026-06: public release. Local-first hybrid retrieval (dense + BM25 + symbol with RRF),
  structural chunking, abstention, MCP/CLI/web surfaces, prebuilt index as a release asset,
  config-driven answer LLM (Anthropic / OpenAI / any OpenAI-compatible local server).
