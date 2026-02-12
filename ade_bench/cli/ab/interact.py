"""Interactive shell command for ADE-bench tasks."""

import logging
import subprocess
import typer
import yaml
from pathlib import Path
from typing import Annotated

from ade_bench.handlers.trial_handler import TrialHandler
from ade_bench.terminal.docker_compose_manager import DockerComposeManager
from ade_bench.utils.logger import logger


def interact(
    task_id: Annotated[str, typer.Option("-t", "--task-id", help="The ID of the task to launch.")],
    db: Annotated[str, typer.Option("--db", help="Database type to use (e.g., duckdb, snowflake)")],
    project_type: Annotated[
        str, typer.Option("--project-type", help="Project type to use (e.g., dbt)")
    ],
    agent: Annotated[
        str,
        typer.Option("--agent", help="Agent to set up (optional)"),
    ] = None,
    step: Annotated[
        str,
        typer.Option(
            "--step",
            help="Point in workflow to start interactive session (post-setup, post-agent, post-eval)",
            case_sensitive=False,
        ),
    ] = "post-setup",
    tasks_dir: Annotated[Path, typer.Option(help="The path to the tasks directory.")] = Path(
        "tasks"
    ),
    include_all: Annotated[
        bool,
        typer.Option(
            "-a",
            "--include-all",
            help="Copy test scripts and solution script to container",
        ),
    ] = False,
    rebuild: Annotated[bool, typer.Option(help="Whether to rebuild the client container.")] = True,
    run_id: Annotated[str, typer.Option(help="Optional run ID for output directory")] = None,
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
    # Validate the step parameter
    valid_steps = ["post-setup", "post-agent", "post-eval"]
    if step.lower() not in valid_steps:
        typer.echo(f"Invalid step: {step}. Valid options are: {', '.join(valid_steps)}")
        raise typer.Exit(1)

    step = step.lower()  # Normalize to lowercase

    # If we're going to run the agent, we must have an agent specified
    if (step == "post-agent" or step == "post-eval") and not agent:
        typer.echo(f"Step '{step}' requires specifying an agent with --agent")
        raise typer.Exit(1)
    # Import necessary modules from harness
    from ade_bench.setup.setup_orchestrator import SetupOrchestrator
    from ade_bench.agents import AgentName
    from datetime import datetime

    # Set up logging
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

    # Configure output directory
    output_path = Path("experiments")
    if not run_id:
        run_id = datetime.now().strftime("%Y-%m-%d__%H-%M-%S")

    # Create the TrialHandler (this mimics what Harness does)
    task_dir = tasks_dir / task_id
    if not task_dir.exists():
        typer.echo(f"Task {task_dir.absolute()} does not exist.")
        raise typer.Exit(code=1)

    # Create the output directory
    output_dir = output_path / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create the trial handler
    trial_handler = TrialHandler(trial_name=task_id, input_path=task_dir, output_path=output_dir)

    # Find the matching variant
    variant_found = False
    for variant in trial_handler.task.variants:
        if variant.db_type == db and variant.project_type == project_type:
            trial_handler.variant_config = variant.model_dump()
            variant_found = True
            break

    if not variant_found:
        typer.echo(f"No variant found for database '{db}' and project type '{project_type}'")
        typer.echo("Available variants:")
        for variant in trial_handler.task.variants:
            typer.echo(f"  - Database: {variant.db_type}, Project Type: {variant.project_type}")
        raise typer.Exit(code=1)

    # Set up Docker container using DockerComposeManager

    typer.echo(f"Setting up container for {task_id} with {db}/{project_type}...")
    docker_manager = DockerComposeManager(
        client_container_name=trial_handler.client_container_name,
        client_image_name=trial_handler.client_image_name,
        docker_compose_path=trial_handler.docker_compose_path,
        docker_name_prefix=trial_handler.docker_image_prefix,
        no_rebuild=not rebuild,
        cleanup=False,  # We don't want to clean up after
        logs_path=trial_handler.sessions_path,
        build_context_dir=trial_handler.input_path,
    )

    # Start the container
    container = docker_manager.start()

    # Create a terminal for setup operations
    from ade_bench.terminal.terminal import Terminal
    from ade_bench.terminal.tmux_session import TmuxSession

    terminal = Terminal(
        client_container_name=trial_handler.client_container_name,
        client_image_name=trial_handler.client_image_name,
        docker_compose_path=trial_handler.docker_compose_path,
        docker_name_prefix=trial_handler.docker_image_prefix,
        sessions_path=trial_handler.sessions_path,
        no_rebuild=True,  # Already built
        cleanup=False,  # We'll handle cleanup
        build_context_dir=trial_handler.input_path,
    )
    # Set both the container and the compose manager's client container
    terminal.container = container
    terminal._compose_manager._client_container = container

    # Create a tmux session directly without using TrialHandler
    session_name = f"task-{task_id}"

    # Patch TmuxSession._recording_path to return None to disable recording

    # Save the original property
    original_recording_path = TmuxSession._recording_path

    # Create a new property that always returns None
    @property
    def no_recording_path(self) -> None:
        return None

    # Apply our patch to disable recording
    TmuxSession._recording_path = no_recording_path

    try:
        # Create the session with recording disabled
        session = TmuxSession(
            container=container,
            session_name=session_name,
            commands_path=None,  # Skip command logging
        )
        session.start()
    except RuntimeError as e:
        # Restore the original recording path property
        TmuxSession._recording_path = original_recording_path

        if "tmux is not installed" in str(e):
            # Try to install tmux
            typer.echo("tmux is not installed in the container. Attempting to install it...")
            result = container.exec_run(["apt-get", "update", "-y"])
            if result.exit_code == 0:
                result = container.exec_run(["apt-get", "install", "-y", "tmux"])
                if result.exit_code == 0:
                    typer.echo("Successfully installed tmux. Retrying session creation...")

                    # Try again with the recording disabled
                    session = TmuxSession(
                        container=container,
                        session_name=session_name,
                        commands_path=None,  # Skip command logging
                    )
                    session.start()
                else:
                    # Restore before exit
                    TmuxSession._recording_path = original_recording_path
                    typer.echo(f"Failed to install tmux: {result.output.decode('utf-8')}")
                    raise typer.Exit(1)
            else:
                # Restore before exit
                TmuxSession._recording_path = original_recording_path
                typer.echo(f"Failed to update package lists: {result.output.decode('utf-8')}")
                raise typer.Exit(1)
        else:
            raise
    finally:
        # Always restore the original recording path property
        TmuxSession._recording_path = original_recording_path

    # Create the file_diff_handler
    file_diff_handler = None

    # Run task setup
    typer.echo("Setting up task environment...")
    setup_orchestrator = SetupOrchestrator(
        logger=logger,
        terminal=terminal,
        session=session,  # Use the tmux session for setup
        file_diff_handler=file_diff_handler,
        trial_handler=trial_handler,
    )

    try:
        # Run database-specific and project-specific setup
        if not setup_orchestrator.setup_task(task_id, trial_handler.variant_config):
            typer.echo("Setup failed. See logs for details.", err=True)
            raise typer.Exit(1)

        # Set up agent if requested
        if agent:
            try:
                agent_name = AgentName(agent.lower())
                typer.echo(f"Setting up agent: {agent_name.value}")

                # Set agent in trial handler
                trial_handler.agent_name = agent_name

                # Setup agent configuration files
                from ade_bench.setup.agent_setup import setup_agent_config

                setup_agent_config(terminal, task_id, trial_handler, logger)

                # Install the agent using the agent's own setup code
                typer.echo(f"Installing {agent_name.value} agent...")

                # Only install for certain agents that need installation
                if agent_name in [AgentName.CLAUDE_CODE, AgentName.MACRO]:
                    from ade_bench.agents.agent_factory import NamedAgentFactory

                    # Create the agent instance
                    agent_instance = NamedAgentFactory(agent_name).get_agent()

                    # For installed agents, we just need to do setup steps from perform_task
                    # without actually running the agent commands
                    if (
                        hasattr(agent_instance, "_install_agent_script")
                        and agent_instance._install_agent_script
                    ):
                        # Copy the installation script
                        session.copy_to_container(
                            agent_instance._install_agent_script,
                            container_dir="/installed-agent",
                            container_filename="install-agent.sh",
                        )

                        # Setup environment variables
                        if hasattr(agent_instance, "_env") and agent_instance._env:
                            import shlex

                            env_setup_content = agent_instance._create_env_setup_file()
                            session.container.exec_run(
                                [
                                    "sh",
                                    "-c",
                                    f"echo {shlex.quote(env_setup_content)} > /installed-agent/setup-env.sh",
                                ],
                            )
                            session.send_keys(
                                ["source /installed-agent/setup-env.sh", "Enter"],
                                block=True,
                            )

                        # Run the installation script
                        session.send_keys(
                            ["source /installed-agent/install-agent.sh", "Enter"],
                            block=True,
                        )

            except ValueError:
                typer.echo(f"Warning: Unknown agent '{agent}', skipping agent setup")
                typer.echo(f"Available agents: {', '.join([a.value for a in AgentName])}")

        for script_path in trial_handler.task.test_script_paths:
            terminal.copy_to_container(
                paths=[script_path],
                container_dir=str(DockerComposeManager.CONTAINER_SCRIPTS_DIR),
                container_filename=script_path.name,
            )

        # Always copy test files for post-agent and post-eval
        if step in ["post-agent", "post-eval"] or include_all:
            typer.echo("Copying solution and test files...")

            # Copy solutions directory if it exists
            if trial_handler.solutions_dir.exists():
                terminal.copy_to_container(
                    paths=[trial_handler.solutions_dir], container_dir="/sage/solutions"
                )

            # Copy test files
            terminal.copy_to_container(
                paths=[
                    trial_handler.run_tests_path,
                    trial_handler.test_dir,
                ],
                container_dir="/tests",
            )

            # Copy solution.sh if it exists
            solution_script = task_dir / "solution.sh"
            if solution_script.exists():
                terminal.copy_to_container(
                    paths=[solution_script], container_dir="/sage", container_filename="solution.sh"
                )

                # Make it executable
                container.exec_run("chmod +x /sage/solution.sh")

            # Copy seeds directory if it exists
            if trial_handler.seeds_dir.exists():
                terminal.copy_to_container(
                    paths=[trial_handler.seeds_dir],
                    container_dir=str(DockerComposeManager.CONTAINER_SEEDS_DIR),
                )
        # For post-agent and post-eval modes, we need to run the agent
        if step in ["post-agent", "post-eval"] and agent:
            typer.echo(f"Running {agent} agent on task {task_id}...")

            # Load the task.yaml to get the prompts
            task_yaml_path = task_dir / "task.yaml"
            if not task_yaml_path.exists():
                typer.echo(f"Task file not found: {task_yaml_path}")
                raise typer.Exit(1)

            with open(task_yaml_path) as f:
                task_data = yaml.safe_load(f)

            # Get the base prompt (first in the list)
            if "prompts" not in task_data or not task_data["prompts"]:
                typer.echo("No prompts found in task.yaml")
                raise typer.Exit(1)

            prompt = task_data["prompts"][0]["prompt"]

            # Run the agent with the prompt
            agent_name = AgentName(agent.lower())
            from ade_bench.harness_models import TerminalCommand

            if agent_name == AgentName.SAGE:
                # For the sage agent, we run the solution script in the tmux session
                typer.echo("Running sage agent (solution.sh)...")

                # Use the standard TerminalCommand with config timeout
                from ade_bench.config import config

                session.send_command(
                    TerminalCommand(
                        command="/sage/solution.sh",
                        block=True,
                        max_timeout_sec=config.default_agent_timeout_sec,
                        append_enter=True,
                    )
                )

                typer.echo(
                    "Solution script sent to tmux session. You'll see the execution in the session."
                )
            else:
                # For other agents, we need to get the agent instance and run it
                from ade_bench.agents.agent_factory import NamedAgentFactory
                from ade_bench.harness_models import TerminalCommand

                # Create the agent instance
                agent_instance = NamedAgentFactory(agent_name=agent_name).get_agent()

                # Ensure log directories exist if needed
                if hasattr(agent_instance, "LOG_DIR") and agent_instance.LOG_DIR:
                    typer.echo(f"Ensuring log directory exists: {agent_instance.LOG_DIR}")
                    session.container.exec_run(["mkdir", "-p", agent_instance.LOG_DIR])

                # Use the agent's _run_agent_commands method to get the correct command
                if hasattr(agent_instance, "_run_agent_commands"):
                    # Get the commands from the agent
                    commands = agent_instance._run_agent_commands(prompt)
                    typer.echo("Running agent commands in tmux session...")

                    # Execute each command through the tmux session's send_command method
                    # exactly as the harness would
                    for cmd in commands:
                        typer.echo(f"Sending command: {cmd.command}")
                        session.send_command(cmd)

                        # Let the user know it's running
                        typer.echo(
                            "Command sent to tmux session. Agent is running in the session..."
                        )
                        typer.echo(
                            "You'll be connected to the tmux session to see the agent in action."
                        )
                else:
                    typer.echo(f"Agent {agent_name.value} does not have _run_agent_commands method")
                    raise typer.Exit(1)

        # For post-eval mode, also run the tests
        if step == "post-eval":
            typer.echo("Running tests...")

            # Run dbt tests
            result = container.exec_run(["/bin/bash", "-c", "cd /app && dbt test"])
            typer.echo(result.output.decode("utf-8"))

            # The test status code indicates whether all tests passed
            if result.exit_code != 0:
                typer.echo("Some tests failed")
            else:
                typer.echo("All tests passed!")

        # Launch interactive shell
        typer.echo(f"\nInteractive environment ready for task {task_id}")
        typer.echo(f"Database: {db}, Project Type: {project_type}")
        if agent:
            typer.echo(f"Agent: {agent}")
        if step != "post-setup":
            typer.echo(f"Step: {step} (agent has already run)")
        typer.echo("Type 'exit' to quit and clean up.")

        # Tell the user about the tmux session
        typer.echo(f"\nTmux session '{session_name}' is active.")
        typer.echo("You can detach from tmux with Ctrl+B, D and reattach with 'tmux attach'")

        # Attach to the tmux session - fall back to normal shell if tmux session is killed
        subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                container.name,
                "bash",
                "-c",
                f"tmux attach -t {session_name} || bash",
            ],
            check=False,
        )

    finally:
        # Clean up
        typer.echo("Cleaning up container...")
        docker_manager.stop()
