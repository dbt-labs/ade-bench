#!/usr/bin/env python3
"""
DEPRECATED: This script is no longer used.

Please use the CLI instead. See the Installation section of the README for setup instructions.
"""

import sys


def main():
    print("""
This script is deprecated and no longer supported.

Please use the CLI instead. See the Installation section of the README for setup instructions:

    pip install -e .
    ade --help

For example:
    ade run simple001 --db duckdb --project-type dbt --agent sage
""")
    sys.exit(1)


if __name__ == "__main__":
    main()
