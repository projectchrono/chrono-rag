# Security and content reports

## Reporting a vulnerability

If you find a security issue (for example in the web backend, the MCP server, or the index
download path), please do not open a public issue with exploit details. Instead use GitHub's
private vulnerability reporting on this repository ("Security" tab, "Report a vulnerability"),
or email the maintainer: negrut@wisc.edu.

You should get an acknowledgment within a week. This is a small research-lab project, not a
staffed security team; severe issues are fixed with priority, best-effort otherwise.

## Scope notes

1. chrono-rag runs locally. The web backend binds to localhost by default and is not meant to
   be exposed to the internet; if you deploy it anyway, put it behind your own auth.
2. Retrieved corpus text is treated as untrusted data: chunks that look like prompt-injection
   attempts are down-ranked and flagged, and the answer prompt instructs the LLM not to follow
   instructions found in context. This reduces, but does not eliminate, injection risk.
3. API keys are read from the environment (or a local `.env`) and are never logged or sent
   anywhere except to the provider you selected.

## Personal-information and content-removal reports

For personal information found in a published index (e.g. the optional forum index), or to
request removal of your forum content, see [DATA.md](DATA.md). Either open a regular issue or
use the email above.
