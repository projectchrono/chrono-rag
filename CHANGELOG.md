# Changelog

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
