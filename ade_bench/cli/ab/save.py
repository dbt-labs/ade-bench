"""Commands for saving ADE-bench results."""

import shutil
import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(
    help="Save ADE-bench results",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _get_most_recent_run_with_results(output_path: Path) -> Optional[Path]:
    """Get the most recent run directory that has results."""
    if not output_path.exists():
        return None

    # Find directories with results.json, sorted by modification time
    runs_with_results = []
    for d in output_path.iterdir():
        if d.is_dir() and (d / "results.json").exists():
            runs_with_results.append(d)

    if not runs_with_results:
        return None

    # Sort by modification time, most recent first
    runs_with_results.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return runs_with_results[0]


def _save_run(run_path: Path, saved_dir: Path, force: bool = False) -> bool:
    """Save a run to the saved directory. Returns True if successful."""
    exp_name = run_path.name
    dest_path = saved_dir / exp_name

    # Check if it already exists
    if dest_path.exists():
        if not force:
            overwrite = typer.confirm(f"{exp_name} already exists in {saved_dir}. Overwrite?")
            if not overwrite:
                typer.echo("Cancelled.")
                return False
        # Remove existing directory
        shutil.rmtree(dest_path)

    # Copy the experiment
    typer.echo(f"Copying {exp_name} to {saved_dir}/...")
    shutil.copytree(run_path, dest_path)
    typer.echo(f"Saved to {dest_path}")
    return True


@app.callback()
def save_callback(
    ctx: typer.Context,
    output_path: Path = typer.Option(
        Path("experiments_saved"), "--output-path", "-o", help="Path to save experiments to"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing saved run without prompting"
    ),
):
    """Save ADE-bench results."""
    # If no subcommand, default to saving most recent run
    if ctx.invoked_subcommand is None:
        _save_most_recent(saved_path=output_path, force=force)


def _save_most_recent(
    output_path: Path = Path("experiments"),
    saved_path: Path = Path("experiments_saved"),
    force: bool = False,
):
    """Save the most recent run with results."""
    run_path = _get_most_recent_run_with_results(output_path)
    if not run_path:
        typer.echo("No experiments with results found.")
        raise typer.Exit(code=1)

    # Create saved directory if it doesn't exist
    saved_path.mkdir(exist_ok=True)

    typer.echo(f"Saving most recent run: {run_path.name}")
    if not _save_run(run_path, saved_path, force):
        raise typer.Exit(code=0)


@app.command("run")
def save_run(
    run_id: Optional[str] = typer.Argument(
        None, help="Run ID to save. If not provided, saves the most recent run."
    ),
    output_path: Path = typer.Option(
        Path("experiments_saved"), "--output-path", "-o", help="Path to save experiments to"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing saved run without prompting"
    ),
):
    """
    Save a run to the experiments_saved directory.

    If no run_id is provided, saves the most recent run with results.
    """
    saved_path = output_path
    experiments_dir = Path("experiments")

    if run_id:
        run_path = experiments_dir / run_id
        if not run_path.exists():
            typer.echo(f"Run {run_id} not found in {experiments_dir}.")
            raise typer.Exit(code=1)
        if not (run_path / "results.json").exists():
            typer.echo(f"Run {run_id} does not have results.json.")
            raise typer.Exit(code=1)
    else:
        run_path = _get_most_recent_run_with_results(experiments_dir)
        if not run_path:
            typer.echo("No experiments with results found.")
            raise typer.Exit(code=1)
        typer.echo(f"Saving most recent run: {run_path.name}")

    # Create saved directory if it doesn't exist
    saved_path.mkdir(exist_ok=True)

    if not _save_run(run_path, saved_path, force):
        raise typer.Exit(code=0)
