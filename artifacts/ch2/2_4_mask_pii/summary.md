# 2.4 Mask PII Audit Summary

These artifacts support the `writeup.md` discussion for Problem `mask_pii` part (5).

Key observations from the 20-sample manual audit:

- Most matches were reasonable on ordinary webpages.
- The clearest false positive came from corrupted PDF-like text, where binary garbage produced strings such as `E@NH.oB` that matched the email regex even though they were not real email addresses.
- We also observed false negatives for phone numbers, including non-US or irregular local formats such as `0577-86809666 86809777` and inconsistent handling of variants like `0321 4115583`.

Archived files:

- `samples.jsonl`: sampled documents with matched spans and masked text.
- `summary.json`: run metadata for the audit script.
- `review_preview.md`: lightweight review-oriented preview generated during manual inspection.
