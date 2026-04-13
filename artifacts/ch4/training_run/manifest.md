# Chapter 4 Training Run Artifacts

Run name: `filtered_cc_5000_train_hopper_100k_20260412_213349`

This directory archives lightweight evidence for the `train_model` writeup section.

## Included

- `training_curves.svg`: train loss, validation loss, and learning-rate schedule plot.
- `training_curves_summary.json`: plot-generation summary and curve metadata.
- `validation_curve.json`: parsed validation-loss curve and best validation loss.
- `validation_curve.md`: Markdown validation-loss table.
- `final_status.txt`: successful completion status, file sizes, and final GPU/disk snapshot.
- `run_metadata.env`: run configuration and paths.
- `training_log_tail.txt`: final log tail for quick audit.
- `model_config.json`: GPT-2-small-shaped model configuration saved by the training script.
- `config.yaml` and `your_data.yaml`: training configuration snapshots.
- `SUCCESS`: empty sentinel showing the wrapper verified artifacts after training.

## Not Included

- Full training log: `/root/autodl-tmp/training/logs/filtered_cc_5000_train_hopper_100k_20260412_213349.log`
- Model checkpoint: `/root/autodl-tmp/training/filtered_cc_5000_train_hopper_100k_20260412_213349/model.pt`
- Tokenized training bin: `/root/autodl-tmp/processed/online_cc_5000_success_counted_20260411_112746/tokenized/filtered_train_gpt2.bin`
- Paloma validation bin: `/root/autodl-tmp/tokenized/tokenized_paloma_c4_100_domains_validation.bin`

These files are intentionally kept out of git because they are large or remote-environment-specific.
