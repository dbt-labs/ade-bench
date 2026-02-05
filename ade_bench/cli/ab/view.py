"""Commands for viewing ADE-bench results."""

import sys
from pathlib import Path
from typing import Annotated

import typer

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from ade_bench.cli.ab import runs as runs_module
from ade_bench.cli.ab import tasks as tasks_module
from scripts_python.view_results import main as view_results_main

app = typer.Typer(
    help="View ADE-bench results",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback()
def view_callback(
    ctx: typer.Context,
    output_path: Annotated[
        Path,
        typer.Option(
            "--output-path",
            "-o",
            help="Path to the output directory",
        ),
    ] = Path("experiments"),
):
    """View ADE-bench results."""
    # If no subcommand, use the existing view_results logic
    if ctx.invoked_subcommand is None:
        view_results_main(output_path=output_path)


# Register runs subcommands directly under view
app.command("run")(runs_module.open)
app.command("runs")(runs_module.list)
app.command("tasks")(tasks_module.list)
