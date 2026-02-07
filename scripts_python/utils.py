#!/usr/bin/env python3
"""Shared utilities for scripts."""

import glob
import os
from pathlib import Path


def get_latest_experiment_with_results(experiments_dir: Path = Path("experiments")) -> Path | None:
    """Find the most recent experiment directory that has results.json."""
    experiments_root = Path(experiments_dir)
    experiments = glob.glob(str(experiments_root / "*"))
    if not experiments:
        return None

    # Sort by creation time, newest first
    experiments_sorted = sorted(experiments, key=os.path.getctime, reverse=True)

    # Find the first one that has results.json
    for exp in experiments_sorted:
        results_file = Path(exp) / "results.json"
        if results_file.exists():
            return Path(exp)

    return None
