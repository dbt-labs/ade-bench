#!/usr/bin/env python3
"""View experiment results using the HTML dashboard."""

import sys
import webbrowser
from pathlib import Path

# Add the project root to the sys path
sys.path.append(str(Path(__file__).parent.parent))

from scripts_python.utils import get_latest_experiment_with_results
from scripts_python.generate_results_html import ResultsHTMLGenerator


def main():
    """Generate HTML dashboard for the latest experiment and open it."""
    # Get the latest experiment with results
    experiment_dir = get_latest_experiment_with_results()
    if not experiment_dir:
        print("Error: No experiments with results found. Run some tests first.")
        sys.exit(1)

    print(f"Using latest experiment: {experiment_dir}")

    # Generate HTML dashboard
    generator = ResultsHTMLGenerator(experiment_dir)
    success = generator.generate_all()

    if success:
        html_path = generator.html_dir / "index.html"
        print(f"Generated HTML dashboard: {html_path}")

        # Open in browser
        webbrowser.open(f"file://{html_path.absolute()}")
        print("Opened in browser")
    else:
        print("Failed to generate HTML dashboard")
        sys.exit(1)


if __name__ == "__main__":
    main()
