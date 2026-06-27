#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASICS_DIR="$REPO_ROOT/cs336-basics"

TRAIN_BIN="${TRAIN_BIN:-data/processed/online_cc_5000_success_counted/tokenized/filtered_train_gpt2.bin}"
VALID_BIN="${VALID_BIN:-data/tokenized/tokenized_paloma_c4_100_domains_validation.bin}"
NPROC_PER_NODE="${NPROC_PER_NODE:-2}"
TRAIN_LOG_DIR="${TRAIN_LOG_DIR:-runs/training/logs}"
RUN_NAME="${RUN_NAME:-your_data_$(date +%Y%m%d_%H%M%S)}"
MODEL_OUTPUT="${MODEL_OUTPUT:-runs/training/$RUN_NAME}"
LOG_PATH="$TRAIN_LOG_DIR/$RUN_NAME.log"
ARTIFACT_DIR="${ARTIFACT_DIR:-$REPO_ROOT/runs/training_artifacts/$RUN_NAME}"
TRAIN_STEPS="${TRAIN_STEPS:-100000}"
EVAL_INTERVAL="${EVAL_INTERVAL:-2000}"
SHUTDOWN_ON_SUCCESS="${SHUTDOWN_ON_SUCCESS:-0}"
SHUTDOWN_DELAY_SECONDS="${SHUTDOWN_DELAY_SECONDS:-60}"
UV_RUN_NO_SYNC="${UV_RUN_NO_SYNC:-0}"

require_file() {
  local path="$1"
  local description="$2"
  if [[ ! -s "$path" ]]; then
    echo "Missing expected $description: $path" >&2
    exit 1
  fi
}

if [[ ! -r "$TRAIN_BIN" ]]; then
  echo "Missing or unreadable training bin: $TRAIN_BIN" >&2
  exit 1
fi

if [[ ! -r "$VALID_BIN" ]]; then
  echo "Missing or unreadable validation bin: $VALID_BIN" >&2
  exit 1
fi

mkdir -p "$TRAIN_LOG_DIR" "$ARTIFACT_DIR"

echo "Training bin: $TRAIN_BIN"
echo "Validation bin: $VALID_BIN"
echo "Model output: $MODEL_OUTPUT"
echo "Processes per node: $NPROC_PER_NODE"
echo "Training log: $LOG_PATH"
echo "Artifact dir: $ARTIFACT_DIR"
echo "Train steps: $TRAIN_STEPS"
echo "Eval interval: $EVAL_INTERVAL"
echo "Shutdown on success: $SHUTDOWN_ON_SUCCESS"
echo "UV run no-sync: $UV_RUN_NO_SYNC"
echo "Extra Hydra overrides: $*"

{
  echo "run_name=$RUN_NAME"
  echo "started_at=$(date -Iseconds)"
  echo "repo_root=$REPO_ROOT"
  echo "basics_dir=$BASICS_DIR"
  echo "train_bin=$TRAIN_BIN"
  echo "valid_bin=$VALID_BIN"
  echo "model_output=$MODEL_OUTPUT"
  echo "training_log=$LOG_PATH"
  echo "artifact_dir=$ARTIFACT_DIR"
  echo "nproc_per_node=$NPROC_PER_NODE"
  echo "train_steps=$TRAIN_STEPS"
  echo "eval_interval=$EVAL_INTERVAL"
  echo "shutdown_on_success=$SHUTDOWN_ON_SUCCESS"
  echo "uv_run_no_sync=$UV_RUN_NO_SYNC"
  echo "git_commit=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
  echo "git_branch=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "extra_hydra_overrides=$*"
} > "$ARTIFACT_DIR/run_metadata.env"

cd "$BASICS_DIR"

uv_run_args=(--project "$REPO_ROOT" --directory "$BASICS_DIR")
if [[ "$UV_RUN_NO_SYNC" == "1" ]]; then
  uv_run_args+=(--no-sync)
fi

hydra_overrides=(
  "paths.train_bin=$TRAIN_BIN"
  "paths.valid_bin=$VALID_BIN"
  "paths.model_output=$MODEL_OUTPUT"
  "+training.train_steps=$TRAIN_STEPS"
  "+training.eval_interval=$EVAL_INTERVAL"
)

set +e
uv run "${uv_run_args[@]}" \
  torchrun --standalone --nproc_per_node="$NPROC_PER_NODE" \
  scripts/train.py \
  --config-name=experiment/your_data \
  "${hydra_overrides[@]}" \
  "$@" 2>&1 | tee "$LOG_PATH"
status=${PIPESTATUS[0]}
set -e

echo "Training exit status: $status"
echo "Training log: $LOG_PATH"

{
  echo "finished_at=$(date -Iseconds)"
  echo "training_exit_status=$status"
} >> "$ARTIFACT_DIR/run_metadata.env"

if [[ "$status" -ne 0 ]]; then
  {
    echo "status=failed"
    echo "reason=torchrun exited with status $status"
    echo "finished_at=$(date -Iseconds)"
  } > "$ARTIFACT_DIR/final_status.env"
  tail -n 200 "$LOG_PATH" > "$ARTIFACT_DIR/training_log_tail.txt" || true
  exit "$status"
fi

require_file "$MODEL_OUTPUT/model.pt" "final model checkpoint"
require_file "$MODEL_OUTPUT/model_config.json" "model config"
require_file "$LOG_PATH" "training log"

uv run "${uv_run_args[@]}" python "$REPO_ROOT/scripts/summarize_training_log.py" "$LOG_PATH" \
  --eval-interval "$EVAL_INTERVAL" \
  --train-steps "$TRAIN_STEPS" \
  --output-json "$ARTIFACT_DIR/validation_curve.json" \
  --output-md "$ARTIFACT_DIR/validation_curve.md" \
  > "$ARTIFACT_DIR/validation_curve.stdout.json"

require_file "$ARTIFACT_DIR/validation_curve.json" "validation curve JSON"
require_file "$ARTIFACT_DIR/validation_curve.md" "validation curve Markdown"
require_file "$ARTIFACT_DIR/validation_curve.stdout.json" "validation curve stdout JSON"

cp "$BASICS_DIR/configs/experiment/your_data.yaml" "$ARTIFACT_DIR/your_data.yaml"
cp "$BASICS_DIR/configs/config.yaml" "$ARTIFACT_DIR/config.yaml"
cp "$MODEL_OUTPUT/model_config.json" "$ARTIFACT_DIR/model_config.json"
tail -n 200 "$LOG_PATH" > "$ARTIFACT_DIR/training_log_tail.txt"

{
  echo "status=success"
  echo "finished_at=$(date -Iseconds)"
  echo "run_name=$RUN_NAME"
  echo "training_exit_status=$status"
  echo "training_log=$LOG_PATH"
  echo "model_output=$MODEL_OUTPUT"
  echo "artifact_dir=$ARTIFACT_DIR"
  echo "model_checkpoint=$MODEL_OUTPUT/model.pt"
  echo "model_config=$MODEL_OUTPUT/model_config.json"
  echo "validation_curve_json=$ARTIFACT_DIR/validation_curve.json"
  echo "validation_curve_md=$ARTIFACT_DIR/validation_curve.md"
  echo
  echo "# Disk"
  df -h "$REPO_ROOT/data" "$REPO_ROOT/runs" 2>/dev/null || true
  echo
  echo "# Key file sizes"
  ls -lh "$TRAIN_BIN" "$VALID_BIN" "$MODEL_OUTPUT/model.pt" "$MODEL_OUTPUT/model_config.json" 2>/dev/null || true
  echo
  echo "# Output sizes"
  du -sh "$MODEL_OUTPUT" "$ARTIFACT_DIR" 2>/dev/null || true
  echo
  echo "# Last GPU snapshot"
  nvidia-smi 2>/dev/null || true
} > "$ARTIFACT_DIR/final_status.txt"

touch "$ARTIFACT_DIR/SUCCESS"
sync

echo "Training artifacts written to: $ARTIFACT_DIR"
echo "Success sentinel: $ARTIFACT_DIR/SUCCESS"

if [[ "$SHUTDOWN_ON_SUCCESS" == "1" ]]; then
  echo "Shutdown requested after successful artifact verification."
  echo "Shutdown will start in $SHUTDOWN_DELAY_SECONDS seconds."
  {
    echo "shutdown_requested_at=$(date -Iseconds)"
    echo "shutdown_delay_seconds=$SHUTDOWN_DELAY_SECONDS"
  } > "$ARTIFACT_DIR/shutdown_requested.env"
  sync
  sleep "$SHUTDOWN_DELAY_SECONDS"
  shutdown -h now || poweroff
fi
