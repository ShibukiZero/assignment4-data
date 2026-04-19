# 2.6 Gopher Quality Filter Audit Summary

These artifacts support the `writeup.md` discussion for Problem `gopher_quality_filters` part (b).

Key observations from the manual audit:

- In a manual review of 20 randomly sampled extracted documents, the Gopher-style rules caught some clearly low-quality cases, including a corrupted PDF-like document and an extremely short page made mostly of icon names.
- The rules also passed several pages that still looked low-value for language-model training, such as a forum registration page, a GitLab topic listing, and a restaurant menu page, because these documents were formally well-structured even though they were dominated by boilerplate or navigation text.
- The strongest language-related failure came from a Chinese novel page that was rejected mainly because too few tokens contained alphabetic characters, highlighting that this heuristic is biased toward English-like text.
- Across all `27,201` eligible extracted documents scanned by the audit script, `23,975` documents (`88.14%`) passed the filter and `3,226` (`11.86%`) were rejected.

Archived files:

- `samples.jsonl`: 20 randomly sampled extracted documents.
- `predictions.jsonl`: per-sample rule diagnostics and pass/reject decisions.
- `summary.json`: corpus-level counts and pass/reject fractions from the audit run.
