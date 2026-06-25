Run a RAG vector search against the chrono-rag backend for this query: $ARGUMENTS

Run the following command and capture the full result:

```bash
bash "$(git rev-parse --show-toplevel)/scripts/rag_search.sh" "$ARGUMENTS"
```

Once you have the result:
1. Extract any ```python ... ``` code blocks from the response and write them to a single file: `scripts/rag_output.py` inside the repo root (use `git rev-parse --show-toplevel` to locate it).
   - If there are multiple code blocks, concatenate them in order, separated by a blank line.
   - If there is no code, do not create the file.
2. Report only the non-code explanation text to the user (strip out the code blocks).
   - At the end, if a file was written, tell the user: "Code written to scripts/rag_output.py"
