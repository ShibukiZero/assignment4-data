# CS336 Spring 2025 Assignment 4: Data

For a full description of the assignment, see the assignment handout at
[cs336_spring2025_assignment4_data.pdf](./cs336_spring2025_assignment4_data.pdf)

If you see any issues with the assignment handout or code, please feel free to
raise a GitHub issue or open a pull request with a fix.

## Setup

This directory is organized as follows:

- [`./cs336-basics`](./cs336-basics): directory containing a module
  `cs336_basics` and its associated `pyproject.toml`. This module contains the staff 
  implementation of the language model from assignment 1. You will use this training code
  to train an LM on your filtered data. You should not modify the training logic, since
  your leaderboard submission must use it exactly.
- [`./cs336_data`](./cs336_data): This folder is basically empty! This is the
  module where you will implement code to filter and process the data.

Visually, it should look something like:

``` sh
.
├── cs336_basics  # A python module named cs336_basics
│   └── ... an optimized training implementation ...
├── cs336_data  # TODO(you): code that you'll write for assignment 4
│   ├── __init__.py
│   └── ... TODO(you): any other files or folders you need for assignment 4 ...
├── README.md
├── pyproject.toml
└── ... TODO(you): other files or folders you need for assignment 4 ...
```

As in previous assignments, we use `uv` to manage dependencies.

## Submitting

To submit, run `./test_and_make_submission.sh` . This script will install your
code's dependencies, run tests, and create a gzipped tarball with the output. We
should be able to unzip your submitted tarball and run
`./test_and_make_submission.sh` to verify your test results.
## Dataset Notes

- `Common Crawl`: this repository's full experiment used `5000` randomly sampled WET files from `CC-MAIN-2026-12`, downloaded from Common Crawl.
- `Wikipedia external links`: this repository used an `extracted_urls.txt.gz` file built from `enwiki-latest-externallinks.sql.gz`, rather than the assignment's fixed extracted URL list.
- `Paloma`: this repository rebuilt the validation bin from open-source Paloma `c4_100_domains` validation `jsonl.gz` files using the GPT-2 tokenizer.
- `Training hardware`: the archived final training run used `2 x NVIDIA H800 PCIe (80 GB)` GPUs.
