# 2.5 Harmful Content Audit Summary

These artifacts support the `writeup.md` discussion for Problem `harmful_content` part (4).

Key observations from the manual audit:

- In a manual review of 20 randomly sampled extracted documents, 19 of 20 classifier decisions matched the human judgment.
- The clearest classifier error was a likely false negative: an Arabic forum thread discussing sexual assault and explicit images was labeled `non-nsfw` and `non-toxic`.
- Across all `27,201` eligible extracted documents scanned by the audit script, `277` documents (`1.02%`) were labeled harmful by at least one classifier.
- Because harmful pages were rare in this slice and some clearly benign pages had only moderate non-harmful confidence, the writeup recommends conservative thresholds and manual review of borderline cases.

Archived files:

- `samples.jsonl`: 20 randomly sampled extracted documents.
- `predictions.jsonl`: classifier outputs for those sampled documents.
- `summary.json`: corpus-level counts and fractions from the audit run.
