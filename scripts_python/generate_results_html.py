#!/usr/bin/env python3
"""Generate HTML results dashboard for experiment results."""

import json
import sys
import html
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add the project root to the sys path
sys.path.append(str(Path(__file__).parent.parent))

from scripts_python.utils import get_latest_experiment_with_results
from scripts_python.render_file_diffs import render_diff_log_html
from scripts_python.summarize_results import generate_html_table
from ade_bench.harness_models import BenchmarkResults


class ResultsHTMLGenerator:
    """Generates HTML dashboard for experiment results."""

    def __init__(self, experiment_dir: Path):
        self.experiment_dir = Path(experiment_dir)
        self.templates_dir = Path(__file__).parent.parent / "templates"
        self.html_dir = self.experiment_dir / "html"

    def generate_all(self):
        """Generate all HTML pages for the experiment."""
        # Create HTML directory
        self.html_dir.mkdir(exist_ok=True)

        # Load experiment data
        experiment_data = self._load_experiment_data()
        if not experiment_data:
            print(f"Error: Could not load experiment data from {self.experiment_dir}")
            return False

        # Generate summary page
        self._generate_summary_page(experiment_data)

        # Generate detail pages for each task
        for task_data in experiment_data['tasks']:
            self._generate_task_detail_pages(task_data)

        return True

    def _load_experiment_data(self) -> Dict[str, Any]:
        """Load experiment data from results.json and run_metadata.json."""
        results_path = self.experiment_dir / "results.json"
        metadata_path = self.experiment_dir / "run_metadata.json"

        if not results_path.exists():
            print(f"Error: results.json not found in {self.experiment_dir}")
            return None

        try:
            with open(results_path, 'r') as f:
                results_data = json.load(f)

            metadata = {}
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

            # Process results into a more usable format
            tasks = []
            for result in results_data.get('results', []):
                # Results are already in the correct format, just use them directly
                tasks.append(result)

            # Note: Most summary stats are now computed in summarize_results()
            # and passed via the 'summary' key. We only compute experiment-level
            # metadata here that isn't available from the results.

            return {
                'experiment_id': self.experiment_dir.name,
                'start_time': metadata.get('start_time', 'Unknown'),
                'experiment_runtime': self._calculate_duration(metadata),
                'agent_from_metadata': metadata.get('agent_name', 'Unknown'),
                'model_from_metadata': metadata.get('model_name'),
                'tasks': tasks
            }

        except Exception as e:
            print(f"Error loading experiment data: {e}")
            return None

    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to a readable string."""
        if seconds < 1:
            return f"{seconds:.2f}s"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        else:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"

    def _format_duration_seconds(self, seconds: float) -> str:
        """Format duration in seconds to H:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    def _calculate_duration(self, metadata: Dict[str, Any]) -> str:
        """Calculate total experiment duration."""
        start_time = metadata.get('start_time')
        end_time = metadata.get('end_time')

        if start_time and end_time:
            try:
                start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration = end - start
                return str(duration).split('.')[0]  # Remove microseconds
            except:
                pass

        return "Unknown"

    def _generate_summary_page(self, experiment_data: Dict[str, Any]):
        """Generate the main summary page."""
        template_path = self.templates_dir / "summary.html"
        if not template_path.exists():
            print(f"Error: Template not found: {template_path}")
            return

        with open(template_path, 'r') as f:
            template_content = f.read()

        # Use the results directly - they're already in the correct format
        benchmark_results = BenchmarkResults(results=experiment_data['tasks'])

        # Generate HTML table and get summary stats (computed once in summarize_results)
        from scripts_python.summarize_results import summarize_results
        summary_data = summarize_results(benchmark_results)
        html_table = generate_html_table(benchmark_results)

        # Extract summary stats
        summary = summary_data['summary']

        # Use model from metadata if available, otherwise use inferred model
        model = experiment_data.get('model_from_metadata') or summary['inferred_model'] or 'Unknown'

        # Use agent from metadata if available, otherwise use from results
        agent = experiment_data.get('agent_from_metadata') or summary['agent'] or 'Unknown'

        # Simple template replacement
        html_content = template_content.replace('{{ experiment_id }}', html.escape(experiment_data['experiment_id']))
        html_content = html_content.replace('{{ start_time }}', html.escape(experiment_data['start_time']))
        html_content = html_content.replace('{{ experiment_runtime }}', html.escape(experiment_data['experiment_runtime']))
        html_content = html_content.replace('{{ total_task_runtime }}', html.escape(self._format_duration_seconds(summary['total_runtime_seconds'])))
        html_content = html_content.replace('{{ total_tasks }}', html.escape(str(summary['total_tasks'])))
        html_content = html_content.replace('{{ successful_tasks }}', html.escape(str(summary['passed_count'])))
        html_content = html_content.replace('{{ failed_tasks }}', html.escape(str(summary['failed_count'])))
        html_content = html_content.replace('{{ errored_tasks }}', html.escape(str(summary['errored_count'])))
        html_content = html_content.replace('{{ success_pct }}', html.escape(f"{summary['success_rate']:.1f}"))
        html_content = html_content.replace('{{ total_cost }}', html.escape(f"${summary['total_cost']:.4f}"))
        html_content = html_content.replace('{{ agent }}', html.escape(agent))
        html_content = html_content.replace('{{ model }}', html.escape(model))
        html_content = html_content.replace('{{ db_type }}', html.escape(summary['db_type'] or 'Unknown'))
        html_content = html_content.replace('{{ project_type }}', html.escape(summary['project_type'] or 'Unknown'))
        html_content = html_content.replace('{{ plugin_set }}', html.escape(summary['plugin_set'] or 'None'))

        # Replace the entire table section with the generated HTML table
        import re
        pattern = r'<table[^>]*>.*?</table>'
        html_content = re.sub(pattern, html_table, html_content, flags=re.DOTALL)

        # Load task.yaml contents and embed as JavaScript object
        task_yamls = self._load_task_yaml_contents(experiment_data)
        task_yamls_js = json.dumps(task_yamls, indent=2)
        task_yamls_script = f"<script>\n        const TASK_YAMLS = {task_yamls_js};\n    </script>"

        # Insert the task yamls script before the closing </head> tag
        html_content = html_content.replace('</head>', f'{task_yamls_script}\n</head>')

        # Write the HTML file
        output_path = self.html_dir / "index.html"
        with open(output_path, 'w') as f:
            f.write(html_content)

        # Copy TSV files to HTML directory
        self._copy_tsv_files()

    def _copy_tsv_files(self):
        """Copy TSV files as plaintext."""
        import shutil

        # Source TSV file
        source_tsv = self.experiment_dir / "results.tsv"

        if not source_tsv.exists():
            print(f"Warning: TSV file not found at {source_tsv}")
            return

        # Copy TSV with headers as .txt
        dest_tsv = self.html_dir / "results_tsv.txt"
        shutil.copy2(source_tsv, dest_tsv)

        # Create TSV without headers as .txt
        with open(source_tsv, 'r') as f:
            lines = f.readlines()

        dest_tsv_no_header = self.html_dir / "results_tsv_no_header.txt"
        if len(lines) > 1:
            with open(dest_tsv_no_header, 'w') as f:
                f.writelines(lines[1:])
        else:
            dest_tsv_no_header.touch()

    def _get_base_task_id(self, task_id: str) -> str:
        """Extract base task ID from variant task ID.

        e.g., 'foo.hard.1-of-1' -> 'foo'
              'foo.base.2-of-3' -> 'foo'
              'foo' -> 'foo'
        """
        # Task variants follow pattern: base_task_id.variant_name.n-of-m
        # Split and check if it looks like a variant
        parts = task_id.split('.')
        if len(parts) >= 2:
            # Check if last part matches n-of-m pattern
            if len(parts) >= 2 and '-of-' in parts[-1]:
                # Return everything except the last two parts (variant name and n-of-m)
                return '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
            # Check if second-to-last part is a known variant name
            # and return the base
            return parts[0]
        return task_id

    def _load_task_yaml_contents(self, experiment_data: Dict[str, Any]) -> Dict[str, str]:
        """Load task.yaml contents for each task and return as a dictionary."""
        tasks_dir = Path(__file__).parent.parent / "tasks"
        task_yamls = {}

        for task_data in experiment_data['tasks']:
            task_id = task_data['task_id']
            base_task_id = self._get_base_task_id(task_id)
            source_yaml = tasks_dir / base_task_id / "task.yaml"

            if source_yaml.exists():
                with open(source_yaml, 'r') as f:
                    task_yamls[task_id] = f.read()
            else:
                task_yamls[task_id] = f"# task.yaml not found for {task_id} (base: {base_task_id})"
                print(f"Warning: task.yaml not found for {task_id} at {source_yaml}")

        return task_yamls

    def _generate_task_detail_pages(self, task_data: Dict[str, Any]):
        """Generate detail pages for a specific task."""
        task_id = task_data['task_id']
        task_base_dir = self.experiment_dir / task_id

        # Find the actual task directory (could be task_id.base.1-of-1, task_id.medium.1-of-1, etc.)
        task_dir = None
        if task_base_dir.exists():
            # Look for subdirectories that match the pattern task_id.*.*
            for subdir in task_base_dir.iterdir():
                if subdir.is_dir() and subdir.name.startswith(f"{task_id}."):
                    task_dir = subdir
                    break

        if not task_dir:
            # Fallback to the base directory if no subdirectory found
            task_dir = task_base_dir

        # Create task HTML directory
        task_html_dir = self.html_dir / task_id
        task_html_dir.mkdir(exist_ok=True)

        # Generate results page
        self._generate_results_page(task_data, task_dir, task_html_dir)

        # Generate panes page
        self._generate_panes_page(task_data, task_dir, task_html_dir)

        # Generate diffs page
        self._generate_diffs_page(task_data, task_dir, task_html_dir)

    def _generate_results_page(self, task_data: Dict[str, Any], task_dir: Path, task_html_dir: Path):
        """Generate results.json detail page."""
        results_path = task_dir / "results.json"
        content = ""

        if results_path.exists():
            with open(results_path, 'r') as f:
                results_data = json.load(f)
            content = json.dumps(results_data, indent=2)
        else:
            content = "No results.json file found."

        self._write_detail_page(
            task_html_dir / "results.html",
            "Results JSON",
            task_data['task_id'],
            content,
            "json"
        )

    def _generate_panes_page(self, task_data: Dict[str, Any], task_dir: Path, task_html_dir: Path):
        """Generate panes detail page.

        Displays terminal output in chronological order:
        1. pre-agent.txt (setup before agent runs)
        2. HTML transcript (if available) OR agent.txt (raw output)
        3. post-agent.txt (teardown after agent completes)
        """
        import shutil

        panes_dir = task_dir / "panes"
        transcript_path = task_dir / "sessions" / "transcript.html"

        # Check for HTML transcript (single well-known file)
        transcript_html = None
        if transcript_path.exists():
            # Copy transcript file to HTML output
            shutil.copy2(transcript_path, task_html_dir / "transcript.html")
            transcript_html = "transcript.html"

        # Build content sections in chronological order
        sections = []

        if panes_dir.exists():
            pane_dict = {p.name: p for p in panes_dir.glob("*.txt")}

            # 1. Pre-agent section
            if "pre-agent.txt" in pane_dict:
                with open(pane_dict["pre-agent.txt"], 'r') as f:
                    pre_content = f.read().strip()
                if pre_content:
                    sections.append(("Pre-Agent Setup", pre_content, "text"))

            # 2. Agent section - HTML transcript OR raw agent.txt
            if transcript_html:
                sections.append(("Agent Transcript", transcript_html, "iframe"))
            elif "agent.txt" in pane_dict:
                with open(pane_dict["agent.txt"], 'r') as f:
                    agent_content = f.read().strip()
                if agent_content:
                    sections.append(("Agent Output", agent_content, "text"))

            # 3. Post-agent section
            if "post-agent.txt" in pane_dict:
                with open(pane_dict["post-agent.txt"], 'r') as f:
                    post_content = f.read().strip()
                if post_content:
                    sections.append(("Post-Agent Output", post_content, "text"))

            # Any other pane files not in the standard order
            other_panes = [p for p in pane_dict.keys()
                          if p not in ["pre-agent.txt", "agent.txt", "post-agent.txt"]]
            for pane_name in sorted(other_panes):
                with open(pane_dict[pane_name], 'r') as f:
                    other_content = f.read().strip()
                if other_content:
                    sections.append((f"Other: {pane_name}", other_content, "text"))

        # Build HTML content from sections
        content_parts = []
        for title, content, content_type in sections:
            if content_type == "iframe":
                content_parts.append(f'''<div style="margin-bottom: 24px;">
    <h2 style="color: #4ec9b0; margin-bottom: 10px;">{html.escape(title)}</h2>
    <iframe src="{html.escape(content)}" style="width: 100%; height: 700px; border: 1px solid #3c3c3c; border-radius: 4px; background: #fff;"></iframe>
    <p style="margin-top: 8px; font-size: 11px; color: #808080;"><a href="{html.escape(content)}" target="_blank" style="color: #9cdcfe;">Open transcript in new tab</a></p>
</div>''')
            else:
                content_parts.append(f'''<div style="margin-bottom: 24px;">
    <h2 style="color: #4ec9b0; margin-bottom: 10px;">{html.escape(title)}</h2>
    <pre style="white-space: pre-wrap; word-wrap: break-word; background: #1e1e1e; padding: 16px; border-radius: 4px; overflow-x: auto;">{html.escape(content)}</pre>
</div>''')

        if not content_parts:
            content_parts.append("<p>No panes data found.</p>")

        # Write directly using template
        self._write_panes_page(
            task_html_dir / "panes.html",
            "Terminal Panes",
            task_data['task_id'],
            "\n".join(content_parts)
        )

    def _generate_diffs_page(self, task_data: Dict[str, Any], task_dir: Path, task_html_dir: Path):
        """Generate diffs detail page."""
        diff_log_path = task_dir / "diffs" / "file_diff_log.txt"
        content = ""

        if diff_log_path.exists():
            # Try to generate HTML diff
            try:
                html_content = render_diff_log_html(diff_log_path, task_data['task_id'])
                # Write the HTML content directly to our task directory
                with open(task_html_dir / "diffs.html", 'w') as f:
                    f.write(html_content)
                return  # We've created the diffs.html file directly
            except Exception as e:
                print(f"Warning: Could not generate HTML diff: {e}")
                # Fall back to text content
                with open(diff_log_path, 'r') as f:
                    content = f.read()
        else:
            content = "No file diff log found."

        self._write_detail_page(
            task_html_dir / "diffs.html",
            "File Diffs",
            task_data['task_id'],
            content,
            "diffs"
        )

    def _write_detail_page(
        self,
        output_path: Path,
        title: str,
        task_id: str,
        content: str,
        content_type: str
    ):
        """Write a detail page using the template.

        Args:
            output_path: Path to write the HTML file
            title: Page title
            task_id: Task identifier
            content: Main text content (will be HTML-escaped)
            content_type: CSS class for content styling
        """
        template_path = self.templates_dir / "detail.html"
        if not template_path.exists():
            print(f"Error: Template not found: {template_path}")
            return

        with open(template_path, 'r') as f:
            template_content = f.read()

        # Simple template replacement
        html_content = template_content.replace('{{ title }}', html.escape(title))
        html_content = html_content.replace('{{ task_id }}', html.escape(task_id))
        html_content = html_content.replace('{{ content }}', html.escape(content))
        html_content = html_content.replace('{{ content_type }}', html.escape(content_type))

        with open(output_path, 'w') as f:
            f.write(html_content)

    def _write_panes_page(
        self,
        output_path: Path,
        title: str,
        task_id: str,
        content_html: str
    ):
        """Write the panes page with pre-built HTML content.

        Unlike _write_detail_page which escapes content, this method accepts
        raw HTML that has already been constructed with proper sections.

        Args:
            output_path: Path to write the HTML file
            title: Page title
            task_id: Task identifier
            content_html: Pre-built HTML content (not escaped)
        """
        template_path = self.templates_dir / "detail.html"
        if not template_path.exists():
            print(f"Error: Template not found: {template_path}")
            return

        with open(template_path, 'r') as f:
            template_content = f.read()

        # Simple template replacement - content_html is already formatted
        html_content = template_content.replace('{{ title }}', html.escape(title))
        html_content = html_content.replace('{{ task_id }}', html.escape(task_id))
        html_content = html_content.replace('{{ content }}', content_html)
        html_content = html_content.replace('{{ content_type }}', 'panes')

        with open(output_path, 'w') as f:
            f.write(html_content)


def main():
    """Main function to generate HTML results."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate HTML results dashboard")
    parser.add_argument("--experiment-dir", type=Path, help="Experiment directory path")

    args = parser.parse_args()

    # Determine experiment directory
    if args.experiment_dir:
        experiment_dir = args.experiment_dir
    else:
        # Use latest experiment with results
        experiment_dir = get_latest_experiment_with_results()
        if not experiment_dir:
            print("Error: No experiments with results found. Run some tests first.")
            sys.exit(1)
        print(f"Using latest experiment: {experiment_dir}")

    # Generate HTML
    generator = ResultsHTMLGenerator(experiment_dir)
    success = generator.generate_all()

    if success:
        print(f"Successfully generated HTML dashboard")
        print(f"Open: {generator.html_dir / 'index.html'}")
    else:
        print("Failed to generate HTML dashboard")
        sys.exit(1)


if __name__ == "__main__":
    main()
