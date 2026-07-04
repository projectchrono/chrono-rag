# Data provenance and privacy

This project ships two kinds of data as downloadable release assets. Neither is committed to
git. This note records where each comes from, what processing is applied, and who to contact
about removal.

## 1. Main index (`chrono-rag-index-*.zip`)

1. Source: the [Project Chrono](https://github.com/projectchrono/chrono) repository at the
   commit recorded in the index `manifest.json` (BSD 3-Clause; see NOTICE).
2. Content: embeddings plus text excerpts (functions, classes, doc sections) of the Chrono
   source, docs, and demos. No personal data beyond what is in the public Chrono repository
   itself.
3. Rebuild: `chrono_rag/preprocess/build_index.py` against any Chrono checkout.

## 2. Optional forum + examples index (`chrono-rag-index-forum-*.zip`)

1. Sources:
   - The [pychrono-examples-10.0](https://github.com/projectchrono/pychrono-examples-10.0)
     example scripts (BSD 3-Clause).
   - Posts from the [ProjectChrono Google Group](https://groups.google.com/g/projectchrono),
     a publicly readable forum. The raw export is a Google Takeout `.mbox` taken from a
     subscribed account; it is never committed or published.
2. Curation at build time (`build_forum_index.py`):
   - Posts older than 2020 are dropped (stale advice for long-gone Chrono versions).
   - Install/build/compile threads are dropped (they go stale fastest).
3. PII scrubbing at build time, before anything is embedded or published:
   - All email addresses are removed.
   - Sender names and opening-greeting names ("Hi X,") are removed.
   - Quoted reply chains, mail-client reply headers, and list footers are stripped.
   - Chunk headers carry only the subject line and date, never a sender.
4. Honest limitation: the scrubbing is heuristic. It reduces, but cannot guarantee the
   absence of, personal information; for example a first name mentioned mid-sentence in a
   post body can survive. The underlying forum is publicly readable, so any residual text is
   already public, but we still treat reports seriously.

## Removal requests

If you find your personal information in a published index, or want a forum post of yours
excluded, open an issue on this repository (you do not need to quote the content itself,
a pointer suffices) or contact the maintainers (see SECURITY.md). We will remove it from the
next published index build and, where warranted, re-publish the current one.
