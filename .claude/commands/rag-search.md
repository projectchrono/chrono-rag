Run a local Chrono/PyChrono retrieval search for: $ARGUMENTS

Run this from the repository root (uses the local index; no API key needed):

```bash
conda run -n chrono-rag python src/surfaces/cli.py search "$ARGUMENTS"
```

Then report the returned chunks (file paths, line numbers, and snippets) to the user.
Results target **PyChrono 10.0**. If the search reports low confidence / insufficient
evidence, tell the user to include a class or function name (e.g. `ChBodyEasyBox`) or the
exact error message.

For an LLM-written answer instead of raw chunks, use the `ask` subcommand instead of
`search` (that path needs an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`).
