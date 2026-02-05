#!/usr/bin/env python3
"""Merge YAML files by deep-merging nested dictionaries."""
import sys
import yaml
from pathlib import Path


def deep_merge(base, merge):
    """Recursively merge two dictionaries."""
    result = base.copy()
    for key, value in merge.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def main():
    if len(sys.argv) != 4:
        print("Usage: merge_yaml.py <base_file> <merge_file> <output_file>")
        sys.exit(1)

    base_file = Path(sys.argv[1])
    merge_file = Path(sys.argv[2])
    output_file = Path(sys.argv[3])

    if not base_file.exists():
        print(f"Error: Base file not found: {base_file}")
        sys.exit(1)

    if not merge_file.exists():
        print(f"Error: Merge file not found: {merge_file}")
        sys.exit(1)

    # Load and merge YAML files
    with open(base_file) as f:
        base_data = yaml.safe_load(f) or {}
    with open(merge_file) as f:
        merge_data = yaml.safe_load(f) or {}

    merged_data = deep_merge(base_data, merge_data)

    # Write merged result
    with open(output_file, "w") as f:
        yaml.dump(merged_data, f, default_flow_style=False, sort_keys=False)

    print(f"Successfully merged {merge_file} into {base_file} -> {output_file}")


if __name__ == "__main__":
    main()
