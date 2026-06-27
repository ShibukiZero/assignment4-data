#!/bin/bash

set -euo pipefail

CRAWL_ID="${1:-CC-MAIN-2026-12}"
COUNT="${2:-50}"
OUTPUT_DIR="${3:-data/raw/${CRAWL_ID}_wet_sample}"
CONCURRENCY="${4:-8}"

BASE_URL="https://data.commoncrawl.org/crawl-data/${CRAWL_ID}"
LISTING_URL="${BASE_URL}/wet.paths.gz"
LISTING_PATH="${OUTPUT_DIR}/wet.paths.gz"
RELATIVE_PATHS_FILE="${OUTPUT_DIR}/sampled_wet_paths.txt"
URLS_FILE="${OUTPUT_DIR}/sampled_wet_urls.txt"

mkdir -p "${OUTPUT_DIR}"

echo "Crawl ID: ${CRAWL_ID}"
echo "Requested sample size: ${COUNT}"
echo "Output directory: ${OUTPUT_DIR}"
echo "Listing URL: ${LISTING_URL}"

curl -LfsS "${LISTING_URL}" -o "${LISTING_PATH}"

if command -v shuf >/dev/null 2>&1; then
    gzip -dc "${LISTING_PATH}" | shuf -n "${COUNT}" > "${RELATIVE_PATHS_FILE}"
else
    gzip -dc "${LISTING_PATH}" \
        | awk 'BEGIN { srand() } { print rand() "\t" $0 }' \
        | sort -k1,1n \
        | head -n "${COUNT}" \
        | cut -f2- \
        > "${RELATIVE_PATHS_FILE}"
fi

sed 's#^#https://data.commoncrawl.org/#' "${RELATIVE_PATHS_FILE}" > "${URLS_FILE}"

START_TIME="$(date +%s)"

if command -v aria2c >/dev/null 2>&1; then
    aria2c \
        --continue=true \
        --max-concurrent-downloads="${CONCURRENCY}" \
        --split=8 \
        --max-connection-per-server=8 \
        --dir="${OUTPUT_DIR}" \
        --input-file="${URLS_FILE}"
else
    xargs -n 1 -P "${CONCURRENCY}" wget -c -P "${OUTPUT_DIR}" < "${URLS_FILE}"
fi

END_TIME="$(date +%s)"
ELAPSED_SECONDS="$((END_TIME - START_TIME))"
if [ "${ELAPSED_SECONDS}" -le 0 ]; then
    ELAPSED_SECONDS=1
fi

DOWNLOADED_FILE_COUNT="$(
    find "${OUTPUT_DIR}" -maxdepth 1 -type f -name '*.warc.wet.gz' | wc -l | tr -d ' '
)"

TOTAL_BYTES="$(
    find "${OUTPUT_DIR}" -maxdepth 1 -type f -name '*.warc.wet.gz' -exec stat -c '%s\n' {} + \
        | awk '{ total += $1 } END { print total + 0 }'
)"

AVG_MIB_PER_SEC="$(
    awk -v bytes="${TOTAL_BYTES}" -v seconds="${ELAPSED_SECONDS}" \
        'BEGIN { printf "%.2f", (bytes / 1048576) / seconds }'
)"

echo
echo "Download summary"
echo "Files downloaded: ${DOWNLOADED_FILE_COUNT}"
echo "Total bytes: ${TOTAL_BYTES}"
echo "Elapsed seconds: ${ELAPSED_SECONDS}"
echo "Average MiB/s: ${AVG_MIB_PER_SEC}"
echo "Sample paths file: ${RELATIVE_PATHS_FILE}"
echo "Sample URLs file: ${URLS_FILE}"
