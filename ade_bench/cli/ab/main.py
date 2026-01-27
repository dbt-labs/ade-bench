"""Main entry point for the ADE-bench CLI."""

import os
import typer
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from ade_bench import Harness
from ade_bench.agents import AgentName
from scripts_python.summarize_results import display_detailed_results

from ade_bench.cli.ab import migrate, check, tasks, view, save, interact as interact_module
import click
from typer import rich_utils

# Default tasks directory - can be overridden via environment variable
DEFAULT_TASKS_DIR = Path(os.environ.get("ADE_TASKS_DIR", "tasks"))

# Store the original error formatter
_original_rich_format_error = rich_utils.rich_format_error


def _custom_rich_format_error(self: click.ClickException) -> None:
    """Custom error formatter that adds a blank line before the error output."""
    from typer.rich_utils import _get_rich_console

    console = _get_rich_console(stderr=True)
    console.print()  # Add blank line before error output
    _original_rich_format_error(self)


# Override typer's error formatter
rich_utils.rich_format_error = _custom_rich_format_error

app = typer.Typer(
    help="ADE-bench: Analytics and Data Engineering Benchmark",
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback()
def main(ctx: typer.Context):
    """ADE-bench: Analytics and Data Engineering Benchmark"""
    if ctx.invoked_subcommand is None:
        raise click.UsageError(
            "Missing command.\n\nTo get help, run:\n\n  ade --help\n  ade <command> --help"
        )


@app.command()
def run(
    tasks: List[str] = typer.Argument(
        ...,
        help="Task ID(s) to run. Use 'all' to run all ready tasks, '@experiment_set' to run an experiment set, 'task+' for wildcards"
    ),
    db: str = typer.Option(
        ...,
        "--db",
        help="Database type to filter variants (e.g., duckdb, postgres, sqlite, snowflake)"
    ),
    project_type: str = typer.Option(
        ...,
        "--project-type",
        help="Project type to filter variants (e.g., dbt, other)"
    ),
    output_path: Path = typer.Option(
        Path("experiments"),
        "--output-path",
        "-o",
        help="Path to the output directory"
    ),
    agent: str = typer.Option(
        "sage",
        "--agent",
        case_sensitive=False,
        help="The agent to benchmark (e.g., sage, claude, macro)"
    ),
    model_name: str = typer.Option(
        "",
        "--model",
        help="The LLM model to use (e.g., claude-3-5-sonnet-20241022, gpt-4)"
    ),
    no_rebuild: bool = typer.Option(
        False,
        "--no-rebuild",
        help="Don't rebuild Docker images"
    ),
    cleanup: bool = typer.Option(
        False,
        "--cleanup",
        help="Cleanup Docker containers and images after running the task"
    ),
    n_concurrent_trials: int = typer.Option(
        4,
        "--n-concurrent-trials",
        help="Maximum number of tasks to run concurrently"
    ),
    exclude_tasks: Optional[List[str]] = typer.Option(
        None,
        "--exclude-tasks",
        help="Task IDs to exclude from the run"
    ),
    n_attempts: int = typer.Option(
        1,
        "--n-attempts",
        help="Number of attempts to make for each task"
    ),
    seed: bool = typer.Option(
        False,
        "--seed",
        help="Extract specified tables as CSV files after harness run completes"
    ),
    agent_args: str = typer.Option(
        "",
        "--agent-args",
        help="Additional arguments to pass to the agent binary (e.g., '--verbose --debug')"
    ),
    no_diffs: bool = typer.Option(
        False,
        "--no-diffs",
        help="Disable file diffing and HTML generation"
    ),
    persist: bool = typer.Option(
        False,
        "--persist",
        help="Keep containers alive when tasks fail for debugging"
    ),
    run_id: str = typer.Option(
        datetime.now().strftime("%Y-%m-%d__%H-%M-%S"),
        "--run-id",
        help="Unique identifier for this harness run"
    ),
    max_episodes: int = typer.Option(
        50,
        "--max-episodes",
        help="The maximum number of episodes (i.e. calls to an agent's LM)"
    ),
    upload_results: bool = typer.Option(
        False,
        "--upload-results",
        help="Upload results to S3 bucket (bucket name is read from config)"
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Set the logging level"
    ),
    use_mcp: bool = typer.Option(
        False,
        "--use-mcp",
        help="Enable MCP (Model Context Protocol) for the agent"
    ),
    use_skills: bool = typer.Option(
        False,
        "--use-skills",
        help="Enable skills for the agent (e.g., dbt-debugging skill)"
    ),
    with_profiling: bool = typer.Option(
        False,
        "--with-profiling",
        help="Run the harness with a python profiler",
    ),
    tasks_dir: Path = typer.Option(
        DEFAULT_TASKS_DIR,
        "--tasks-dir",
        help="Path to the tasks directory (default: ADE_TASKS_DIR env var or 'tasks')"
    )
):
    """
    Run ADE-bench with specified tasks and configuration.

    Example:
    ab run airbnb001 --db duckdb --project-type dbt --agent sage
    """
    # Convert log level string to int
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    # Check for common mistakes in task_ids that look like flags
    flag_looking_args = [task for task in tasks if task.startswith("run-id") or task.startswith("--")]
    if flag_looking_args:
        typer.echo(f"Warning: Some task IDs look like they might be flags: {', '.join(flag_looking_args)}")
        typer.echo("If you meant to use these as options, make sure to use '--option value' format.")
        if not typer.confirm("Continue anyway?"):
            typer.echo("Aborting.")
            raise typer.Exit(code=1)

    # Convert agent string to AgentName enum
    # Check for renamed agent
    if agent.lower() == "oracle":
        typer.echo("Error: The 'oracle' agent has been renamed to 'sage'.")
        typer.echo("Please use --agent sage instead.")
        raise typer.Exit(code=1)

    try:
        agent_name = AgentName(agent.lower())
    except ValueError:
        typer.echo(f"Error: Invalid agent name '{agent}'")
        typer.echo(f"Available agents: {', '.join([a.value for a in AgentName])}")
        raise typer.Exit(code=1)

    # Setup path variables
    dataset_path = tasks_dir
    task_ids = tasks

    if len(tasks) == 1 and tasks[0].lower() == "all":
        task_ids = None

    agent_kwargs = {}

    if agent_name == AgentName.SAGE:
        agent_kwargs["dataset_path"] = dataset_path
    elif agent_args:
        agent_kwargs["additional_args"] = agent_args

    # Create and run the harness
    harness = Harness(
        dataset_path=dataset_path,
        output_path=output_path,
        run_id=run_id,
        agent_name=agent_name,
        model_name=model_name,
        agent_kwargs=agent_kwargs,
        no_rebuild=no_rebuild,
        cleanup=cleanup,
        log_level=log_level_int,
        task_ids=task_ids,
        max_episodes=max_episodes,
        upload_results=upload_results,
        n_concurrent_trials=n_concurrent_trials,
        exclude_task_ids=set(exclude_tasks) if exclude_tasks else None,
        n_attempts=n_attempts,
        create_seed=seed,
        disable_diffs=no_diffs,
        db_type=db,
        project_type=project_type,
        keep_alive=persist,
        use_mcp=use_mcp,
        use_skills=use_skills,
        with_profiling=with_profiling
    )

    results = harness.run()
    display_detailed_results(results)


@app.command()
def interact(
    task_id: str = typer.Option(
        ...,
        "-t", "--task-id",
        help="The ID of the task to launch."
    ),
    db: str = typer.Option(
        ...,
        "--db",
        help="Database type to use (e.g., duckdb, snowflake)"
    ),
    project_type: str = typer.Option(
        ...,
        "--project-type",
        help="Project type to use (e.g., dbt)"
    ),
    agent: str = typer.Option(
        None,
        "--agent",
        help="Agent to set up (optional)",
    ),
    step: str = typer.Option(
        "post-setup",
        "--step",
        help="Point in workflow to start interactive session (post-setup, post-agent, post-eval)",
        case_sensitive=False
    ),
    tasks_dir: Path = typer.Option(
        DEFAULT_TASKS_DIR,
        "--tasks-dir",
        help="Path to the tasks directory (default: ADE_TASKS_DIR env var or 'tasks')"
    ),
    include_all: bool = typer.Option(
        False,
        "-a", "--include-all",
        help="Copy test scripts and solution script to container",
    ),
    rebuild: bool = typer.Option(
        True,
        "--rebuild/--no-rebuild",
        help="Whether to rebuild the client container."
    ),
    run_id: str = typer.Option(
        None,
        "--run-id",
        help="Optional run ID for output directory"
    ),
):
    """
    Launch an interactive shell into a task environment.

    This command sets up the task environment exactly like the harness would,
    then drops you into an interactive shell for debugging.

    The --step option allows controlling how far into the process to run before
    launching the interactive session:
    - post-setup: Start after environment setup (default)
    - post-agent: Start after the agent has run on the task
    - post-eval: Start after tests have been run to evaluate the agent
    """
    # Delegate to the interact module
    interact_module.interact(
        task_id=task_id,
        db=db,
        project_type=project_type,
        agent=agent,
        step=step,
        tasks_dir=tasks_dir,
        include_all=include_all,
        rebuild=rebuild,
        run_id=run_id,
    )


if __name__ == "__main__":
    app()

# Add sub-commands
app.add_typer(migrate.app, name="migrate")
app.add_typer(view.app, name="view")
app.add_typer(save.app, name="save")
app.add_typer(check.app, name="check")
