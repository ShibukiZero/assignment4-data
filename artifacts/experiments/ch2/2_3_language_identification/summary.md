# Section 2.3 Language Identification Summary

## Purpose

These artifacts support the `writeup.md` answers for `Problem language_identification`, especially part `(c)`.

## Archived Files

- `samples.jsonl`
- `predictions.jsonl`
- `human_labels.jsonl`
- `audit_run.log`

## Main Findings

- Manual review covered 20 randomly sampled extracted documents.
- The classifier agreed with the validated human labels on 19 of 20 samples.
- The clearest failure was sample 3, which looked like corrupted PDF/binary garbage but was predicted as English with confidence `0.1513`.
- The manually labeled English fraction was `11/20 = 55%`.
- A confidence threshold around `0.4` was judged to be a reasonable starting point for filtering in this small audit.

## Provenance

- `samples.jsonl`, `predictions.jsonl`, and `audit_run.log` were copied from `runs/langid_audit/` and a terminal log.
- `human_labels.jsonl` records the validated manual labels used to draft the writeup summary.
