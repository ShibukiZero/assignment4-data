#!/usr/bin/env bash
set -euo pipefail

RAW_GLOB="${1:-data/raw/CC-MAIN-2026-12_wet_sample/*.warc.wet.gz}"
RUN_DIR="${2:-runs/chapter4_50wet_pipeline_$(date +%Y%m%d_%H%M%S)}"

STAGE1_WORKERS="${STAGE1_WORKERS:-24}"
STAGE2_WORKERS="${STAGE2_WORKERS:-24}"
PHASE3_CHUNK_DOCS="${PHASE3_CHUNK_DOCS:-1000}"
TOKENIZER="${TOKENIZER:-data/tokenizers/gpt2}"
TOKENIZE_BATCH_SIZE="${TOKENIZE_BATCH_SIZE:-256}"

STAGE1_DIR="${RUN_DIR}/stage1"
STAGE2_DIR="${RUN_DIR}/stage2"
TOKENIZED_DIR="${RUN_DIR}/tokenized"
TOKENIZED_BIN="${TOKENIZED_DIR}/filtered_train_gpt2.bin"
TOKENIZED_SUMMARY="${TOKENIZED_DIR}/filtered_train_gpt2.summary.json"

echo "Run directory: ${RUN_DIR}"
echo "Raw WET glob: ${RAW_GLOB}"
echo

echo "== Stage 1: document-local filtering =="
uv run python scripts/filter_cc_wet_stage1.py \
  --input-glob "${RAW_GLOB}" \
  --output-dir "${STAGE1_DIR}" \
  --workers "${STAGE1_WORKERS}"

echo
echo "== Stage 2: exact-line + MinHash deduplication =="
uv run python scripts/dedup_stage2.py \
  --input-glob "${STAGE1_DIR}/kept_docs/*.jsonl" \
  --output-dir "${STAGE2_DIR}" \
  --workers "${STAGE2_WORKERS}" \
  --phase3-chunk-docs "${PHASE3_CHUNK_DOCS}"

echo
echo "== Stage 3: GPT-2 tokenization =="
uv run python scripts/tokenize_filtered_data.py \
  --input-glob "${STAGE2_DIR}/deduped_docs/*.jsonl" \
  --output-path "${TOKENIZED_BIN}" \
  --summary-path "${TOKENIZED_SUMMARY}" \
  --tokenizer "${TOKENIZER}" \
  --batch-size "${TOKENIZE_BATCH_SIZE}"

echo
echo "Pipeline complete."
echo "Stage 1 summary: ${STAGE1_DIR}/aggregate_summary.json"
echo "Stage 2 summary: ${STAGE2_DIR}/aggregate_summary.json"
echo "Tokenized train bin: ${TOKENIZED_BIN}"
echo "Tokenization summary: ${TOKENIZED_SUMMARY}"
