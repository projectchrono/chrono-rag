Run a local Chrono/PyChrono retrieval search for: $ARGUMENTS

Run this from the repository root (uses the local index; no API key needed):

```bash
conda run -n chrono-rag chrono-rag search "$ARGUMENTS"
```

Then report the returned chunks (file paths, line numbers, and snippets) to the user.
Results target the Chrono checkout named in the printed scope line (by default a dated snapshot
of Chrono main); report that scope to the user. If the search reports low confidence / insufficient
evidence, tell the user to include a class or function name (e.g. `ChBodyEasyBox`) or the
exact error message.

For an LLM-written answer instead of raw chunks, use the `ask` subcommand instead of
`search` (that path needs an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, or a local server
via `CHRONO_RAG_LLM_*`). If the setup seems broken, run `chrono-rag doctor` and report
its output.
