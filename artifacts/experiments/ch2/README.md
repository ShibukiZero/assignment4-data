# Chapter 2 Artifacts

This directory archives the evidence currently used by `writeup.md` for the completed Chapter 2 sections.

## Contents

- `2_2_extract_text/`
  - Raw comparison outputs between our extractor and the matching Common Crawl WET record.
- `2_3_language_identification/`
  - Randomly sampled extracted documents, classifier predictions, the audit run log, and the validated manual labels used for the writeup summary.
- `2_4_mask_pii/`
  - Randomly sampled documents with masking applied, plus a short audit summary of the false positives and false negatives discussed in the writeup.
- `2_5_harmful_content/`
  - Randomly sampled extracted documents, harmful-content classifier predictions, corpus-level summary statistics, and a short audit summary used for the writeup.
- `2_6_gopher_quality_filters/`
  - Randomly sampled extracted documents, rule-based quality-filter diagnostics, corpus-level pass/reject statistics, and a short audit summary used for the writeup.

## Provenance

These files were copied or summarized from temporary working materials under `.agents/logs/` so that the writeup no longer depends on ephemeral collaboration logs.
