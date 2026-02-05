import asyncio
import logging
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

import tempfile
import time
import boto3
from tenacity import RetryError
import json
import cProfile

from ade_bench.agents.agent_factory import AgentFactory
from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.base_agent import AgentResult, BaseAgent
from ade_bench.config import config as ade_bench_config
from ade_bench.handlers.asciinema_handler import AsciinemaHandler
from ade_bench.handlers.file_diff_handler import FileDiffHandler, FileSnapshot
from ade_bench.handlers.trial_handler import TrialHandler
from ade_bench.harness_models import (
    BenchmarkResults,
    FailureMode,
    RunMetadata,
    TrialResults,
)
from ade_bench.models.plugin_set import PluginSet
from ade_bench.plugins.loader import PluginSetLoader
from ade_bench.setup.setup_orchestrator import SetupOrchestrator
from ade_bench.llms.base_llm import ContextLengthExceededError, ParseError
from ade_bench.parsers.base_parser import UnitTestStatus, ParserResult
from ade_bench.terminal.docker_compose_manager import DockerComposeManager
from ade_bench.terminal.terminal import Terminal, spin_up_terminal
from ade_bench.terminal.tmux_session import TmuxSession
from ade_bench.utils.dataset import Dataset
from ade_bench.utils.logger import logger, log_harness_info, rich_logger, initialize_dynamic_logging
from ade_bench.utils.test_generator import generate_solution_tests
from ade_bench.utils.timeout_manager import TimeoutManager
from ade_bench.utils.debug_breakpoint import breakpoint, DebugBreakpointException
from ade_bench.utils.results_writer import write_results_tsv


class Harness:
    def __init__(
        self,
        dataset_path: Path,
        output_path: Path,
        run_id: str,
        agent_name: AgentName,
        model_name: str | None = None,
        agent_kwargs: dict[str, Any] | None = None,
        no_rebuild: bool = False,
        cleanup: bool = False,
        log_level: int = logging.INFO,
        task_ids: list[str] | None = None,
        max_episodes: int = 50,
        upload_results: bool = False,
        n_concurrent_trials: int = 4,
        exclude_task_ids: set[str] | None = None,
        n_attempts: int = 1,
        create_seed: bool = False,
        disable_diffs: bool = False,
        db_type: str | None = None,
        project_type: str | None = None,
        keep_alive: bool = False,
        plugin_set_names: list[str] | None = None,
        with_profiling: bool = False,
    ):
        """
        Runs the Terminal-Bench harness.

        Args:
            dataset_path: The path to the dataset.
            output_path: The path to the output directory. Results and logs will be
                written here.
            run_id: The ID of the run.
            agent_name: The name of the agent to use to generate commands.
            model_name: The name of the model to use for the agent.
            agent_kwargs: Additional keyword arguments to pass to the agent.
            no_rebuild: Whether to avoid rebuilding the Docker image.
            cleanup: Whether to remove the Docker image after the run.
            log_level: The logging level to use (debug, info, warning, error, critical).
            task_ids: The IDs of the tasks to run. If None, all tasks will be run.
            max_episodes: The maximum number of episodes to run for the
                interactive agent.
            upload_results: Whether to upload results to S3.
                The bucket name is read from config.
            n_concurrent_trials: Maximum number of tasks to run concurrently.
            exclude_task_ids: List of task IDs to exclude from the run.
            n_attempts: Number of attempts to make for each task.
            disable_diffs: If True, disables file diffing and HTML generation.
            db_type: Database type to filter variants (e.g., duckdb, postgres, sqlite, snowflake).
            project_type: Project type to filter variants (e.g., dbt, other).
            keep_alive: If True, keep containers alive when tasks fail for debugging.
            plugin_set_names: List of skill set names to use. If None, uses defaults.
            with_profiling: If True, will enable the cProfiler.
        """
        self._run_uuid = None
        self._start_time = datetime.now(timezone.utc).isoformat()

        self._dataset_path = dataset_path
        self._task_ids = task_ids
        self._exclude_task_ids = exclude_task_ids
        self._create_seed = create_seed
        self._disable_diffs = disable_diffs
        self._db_filter = db_type
        self._project_type_filter = project_type
        self._keep_alive = keep_alive
        self._plugin_set_names = plugin_set_names
        self._plugin_sets: list[PluginSet] = []
        self._current_plugin_set: PluginSet | None = None
        self._with_profiling = with_profiling

        # Initialize setup orchestrator for variant-specific setup
        self._setup_orchestrator = SetupOrchestrator()

        self._output_path = output_path
        self._agent_name = agent_name
        self._model_name = AgentName.model_name_from_agent_name(model_name, agent_name)
        self._agent_kwargs = agent_kwargs or {}
        self._run_id = run_id
        self._no_rebuild = no_rebuild
        self._cleanup = cleanup
        self._log_level = log_level
        self._max_episodes = max_episodes
        self._upload_results = upload_results
        self._s3_bucket = ade_bench_config.s3_bucket_name
        self._n_concurrent_trials = n_concurrent_trials
        self._n_attempts = n_attempts

        self._init_dataset()
        self._init_plugin_sets()
        self._init_logger()

    @property
    def _run_path(self) -> Path:
        return self._output_path / self._run_id

    @property
    def _results_output_path(self) -> Path:
        return self._run_path / "results.json"

    @property
    def _run_metadata_output_path(self) -> Path:
        return self._run_path / "run_metadata.json"

    @property
    def _log_output_path(self) -> Path:
        return self._run_path / "run.log"

    @property
    def profiler_output_path(self) -> Path:
        # TODO: for now the path will be hardcoded in the future let's make this configurable
        return Path("profiling/summaries/" + self._run_id + "/")

    @property
    def _cProfile_output_path(self) -> Path:
        return self.profiler_output_path / "cProfile.prof"

    @property
    def _profiler_metadata_output_path(self) -> Path:
        return self.profiler_output_path / "metatdata.json"

    def _create_agent_for_task(self, task_id: str) -> BaseAgent:
        """Create a fresh agent for a specific task.

        Args:
            task_id: The ID of the task to create an agent for.

        Returns:
            A newly initialized agent.
        """
        agent_kwargs = self._agent_kwargs.copy()

        if self._agent_name == AgentName.SAGE:
            agent_kwargs["task_ids"] = [task_id]

        # Pass model_name to agents (if provided)
        if self._model_name:
            agent_kwargs["model_name"] = self._model_name

        # Pass allowed_tools from current plugin set
        if self._current_plugin_set and self._current_plugin_set.allowed_tools:
            agent_kwargs["allowed_tools"] = self._current_plugin_set.allowed_tools

        # Pass mcp_servers from current plugin set
        if self._current_plugin_set and self._current_plugin_set.mcp_servers:
            agent_kwargs["mcp_servers"] = self._current_plugin_set.mcp_servers

        return AgentFactory.get_agent(self._agent_name, **agent_kwargs)

    def _init_dataset(self) -> None:
        # Always use the same Dataset constructor - it handles both cases internally
        self._dataset = Dataset(
            dataset_path=self._dataset_path,
            task_ids=self._task_ids,
            excluded_task_ids=self._exclude_task_ids,
        )

    def _init_plugin_sets(self) -> None:
        """Load and resolve plugin sets from configuration."""
        config_path = self._dataset_path.parent / "experiment_sets" / "plugin-sets.yaml"
        if not config_path.exists():
            # No plugin sets config - use empty list (no plugins)
            self._plugin_sets = [PluginSet(name="no-plugins", allowed_tools=["Bash", "Edit", "Write", "Read", "Glob", "Grep"])]
            return

        loader = PluginSetLoader(config_path)
        self._plugin_sets = loader.resolve_plugin_sets(
            plugin_set_names=self._plugin_set_names,
            agent_name=self._agent_name.value
        )

    def _init_logger(self) -> None:
        """Initialize console logging. File logging is initialized per plugin set."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._log_level)
        logger.addHandler(console_handler)

        self._logger = logger.getChild(__name__)
        self._file_handler: logging.FileHandler | None = None

    def _init_file_logger(self) -> None:
        """Initialize or reinitialize file logging for the current run path."""
        # Remove existing file handler if present
        if self._file_handler is not None:
            logger.removeHandler(self._file_handler)
            self._file_handler.close()

        # Create new file handler for the current run path
        self._file_handler = logging.FileHandler(self._log_output_path)
        self._file_handler.setLevel(logging.DEBUG)
        logger.addHandler(self._file_handler)

    def _is_resolved(self, parser_result: ParserResult | None) -> bool:
        if parser_result is None:
            return False

        parser_results = parser_result.test_results

        # Check if compilation failed
        if "dbt_compile" in parser_results and parser_results["dbt_compile"] == UnitTestStatus.FAILED:
            return False

        # Count the number of tests (excluding the compile test)
        test_results = {k: v for k, v in parser_results.items() if k != "dbt_compile"}
        if not test_results:
            return False

        # Count passing tests
        passing_tests = sum(1 for result in test_results.values() if result == UnitTestStatus.PASSED)
        total_tests = len(test_results)

        # Check if we have fewer parsed tests than expected
        # This catches cases where tests crashed/panicked before producing output
        if parser_result.expected_test_count is not None:
            if total_tests < parser_result.expected_test_count:
                self._logger.debug(
                    f"Task failed: only {total_tests} test results found, "
                    f"but {parser_result.expected_test_count} tests were expected"
                )
                return False

        # For now, require all tests to pass. This could be made configurable per task
        # if we want to allow partial success thresholds
        return passing_tests == total_tests

    def _setup_test_env(self, terminal: Terminal, trial_handler: TrialHandler) -> None:
        # Create a trial-specific temp directory for tests to avoid race conditions
        # when multiple variants of the same task run concurrently
        with tempfile.TemporaryDirectory() as temp_test_dir:
            temp_test_path = Path(temp_test_dir) / "tests"
            temp_test_path.mkdir()

            # Copy existing tests from the shared test directory (excluding AUTO_* files
            # which will be regenerated)
            if trial_handler.test_dir.exists():
                for test_file in trial_handler.test_dir.iterdir():
                    if test_file.is_file() and not test_file.name.startswith("AUTO_"):
                        shutil.copy2(test_file, temp_test_path / test_file.name)

            # Generate solution tests in the temp directory
            if trial_handler.task.solution_seeds:
                self._generate_solution_tests(trial_handler, temp_test_path)

                # Also write the generated tests back to the shared directory as a log
                # of what was generated (useful for debugging). This is safe because we
                # copy from temp_test_path to the container, not from the shared directory.
                # Clear existing AUTO tests first, then copy new ones.
                shared_test_dir = trial_handler.test_dir
                shared_test_dir.mkdir(parents=True, exist_ok=True)
                for auto_test in shared_test_dir.glob("AUTO_*.sql"):
                    try:
                        auto_test.unlink()
                    except OSError:
                        pass  # Ignore errors if another process deleted it
                for test_file in temp_test_path.glob("AUTO_*.sql"):
                    try:
                        shutil.copy2(test_file, shared_test_dir / test_file.name)
                    except OSError:
                        pass  # Ignore errors if another process is writing

            # Copy test-related files from temp directory
            terminal.copy_to_container(
                paths=[
                    trial_handler.agent_pane_path,
                    trial_handler.run_tests_path,
                    temp_test_path,
                ],
                container_dir=str(DockerComposeManager.CONTAINER_TEST_DIR),
            )

            # Copy test scripts to the scripts directory
            for script_path in trial_handler.task.test_script_paths:
                terminal.copy_to_container(
                    paths=[script_path],
                    container_dir=str(DockerComposeManager.CONTAINER_SCRIPTS_DIR),
                    container_filename=script_path.name
                )

            # Copy seeds directory if it exists
            if trial_handler.seeds_dir.exists():
                terminal.copy_to_container(
                    paths=[trial_handler.seeds_dir],
                    container_dir=str(DockerComposeManager.CONTAINER_SEEDS_DIR),
                )

            # Copy solutions directory if it exists
            if trial_handler.solutions_dir.exists():
                terminal.copy_to_container(
                    paths=[trial_handler.solutions_dir],
                    container_dir=str(DockerComposeManager.CONTAINER_SOLUTIONS_DIR),
                )

            # Handle test_setup script if it exists
            if trial_handler.task.test_setup:
                test_setup_path = Path(temp_test_dir) / "test-setup.sh"

                with open(test_setup_path, 'w') as f:
                    f.write("#!/bin/bash\n")
                    f.write(trial_handler.task.test_setup)
                    f.write("\n")

                # Copy the test-setup script to the container
                terminal.copy_to_container(
                    paths=[test_setup_path],
                    container_dir=str(DockerComposeManager.CONTAINER_SCRIPTS_DIR),
                    container_filename="test-setup.sh"
                )
                # Make it executable using the container's exec_run method
                terminal.container.exec_run(f"chmod +x {DockerComposeManager.CONTAINER_SCRIPTS_DIR}/test-setup.sh")

    def _run_tests(
        self,
        terminal: Terminal,
        session: TmuxSession,
        trial_handler: TrialHandler,
    ) -> FailureMode:
        """Run tests with proper timeout management."""
        self._setup_test_env(terminal, trial_handler)

        # Get timeouts for this task
        timeouts = TimeoutManager.get_timeouts_for_task(trial_handler.task)

        try:
            # TODO: This seems like a bad hack.
            # I have no idea why this is needed, but without it, the test run fails?
            time.sleep(2)

            # Log that test script is starting to run
            log_harness_info(self._logger, trial_handler.task_id, "eval", "Executing test script...")

            # Build command with optional parameters
            command = f"bash {DockerComposeManager.CONTAINER_TEST_DIR / trial_handler.run_tests_path.name}"

            db_type = trial_handler.variant_config.get('db_type')
            project_type = trial_handler.variant_config.get('project_type')

            if db_type:
                command += f" --db-type={db_type}"
            if project_type:
                command += f" --project-type={project_type}"

            session.send_keys([command, "Enter"], block=True, max_timeout_sec=timeouts.test_execution)

        except TimeoutError:
            self._logger.warning(
                f"Test command timed out after "
                f"{timeouts.test_execution}s for task "
                f"{trial_handler.task_id}."
            )

            # Update logger table
            log_harness_info(
                self._logger,
                trial_handler.task_id,
                "done",
                f"TIMEOUT - test execution timed out after {timeouts.test_execution} seconds"
            )

            # Kill the session to stop the test
            try:
                session.kill_session()
                self._logger.info(f"Killed test session for timed-out task {trial_handler.task_id}")
            except Exception as e:
                self._logger.error(f"Failed to kill session after test timeout: {e}")

            return FailureMode.TEST_TIMEOUT

        return FailureMode.NONE

    def _generate_solution_tests(self, trial_handler: TrialHandler, target_dir: Path) -> None:
        """Generate solution tests for tables specified in solution_seeds.

        Args:
            trial_handler: The trial handler containing task configuration
            target_dir: Directory to write generated tests to
        """
        if not trial_handler.task.solution_seeds:
            return

        log_harness_info(self._logger, trial_handler.task_id, "eval", f"Generating solution tests...")

        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Generate tests for each solution seed
        for config in trial_handler.task.get_solution_seed_configs():
            try:
                generate_solution_tests(config.table_name, target_dir, config)
            except Exception as e:
                self._logger.error(f"Failed to generate tests for {config.table_name}: {e}")

    def _parse_results(
        self,
        trial_handler: TrialHandler,
        post_agent_pane: str,
    ) -> tuple[ParserResult | None, FailureMode]:
        try:
            parser_result = trial_handler.parser.parse(post_agent_pane)

            # Log the status message if it exists
            if parser_result.status_message:
                log_harness_info(self._logger, trial_handler.task_id, "done", parser_result.status_message)
            else:
                log_harness_info(self._logger, trial_handler.task_id, "done", "No status message found.")

            return parser_result, FailureMode.NONE
        except Exception as e:
            self._logger.error(
                f"Error parsing results for task {trial_handler.task_id}: {e}. It's "
                "possible that the tests failed to run. Inspect post-agent.txt for "
                "more information."
            )
            return None, FailureMode.PARSE_ERROR

    async def _run_agent_with_timeout(
        self,
        trial_handler: TrialHandler,
        session: TmuxSession,
        logging_dir: Path,
        agent: BaseAgent,
        task_name: str | None = None,
        prompt_suffix: str = "",
    ) -> AgentResult | None:
        timeouts = TimeoutManager.get_timeouts_for_task(trial_handler.task)

        # Build the full prompt with optional suffix
        full_prompt = trial_handler.task_prompt
        if prompt_suffix:
            full_prompt = f"{full_prompt}\n\n{prompt_suffix}"

        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(
            None,
            partial(
                agent.perform_task,
                task_prompt=full_prompt,
                session=session,
                logging_dir=logging_dir,
                task_name=task_name,
            ),
        )

        # Use the composite timeout that includes all agent operations
        return await asyncio.wait_for(task, timeout=timeouts.total_agent_operation)

    def _run_agent(
        self,
        session: TmuxSession,
        trial_handler: TrialHandler,
        agent: BaseAgent,
        task_name: str | None = None,
    ) -> tuple[AgentResult | None, FailureMode]:
        try:
            # Get prompt suffix from current plugin set
            prompt_suffix = ""
            if self._current_plugin_set and self._current_plugin_set.prompt_suffix:
                prompt_suffix = self._current_plugin_set.prompt_suffix

            result = asyncio.run(
                self._run_agent_with_timeout(
                    trial_handler=trial_handler,
                    session=session,
                    logging_dir=trial_handler.agent_logging_dir,
                    agent=agent,
                    task_name=task_name,
                    prompt_suffix=prompt_suffix,
                )
            )

            if result is None:
                return None, FailureMode.UNKNOWN_AGENT_ERROR

            return result, result.failure_mode

        except asyncio.TimeoutError:
            timeouts = TimeoutManager.get_timeouts_for_task(trial_handler.task)
            self._logger.warning(
                f"Agent execution timed out after "
                f"{timeouts.total_agent_operation}s for task "
                f"{trial_handler.task_id}. "
                f"This is the total operation timeout (not agent setup). "
                f"(Breakdown: setup={timeouts.setup}s, "
                f"execution={timeouts.agent_execution}s, "
                f"cleanup={timeouts.cleanup}s)"
            )

            # Update logger table
            log_harness_info(
                self._logger,
                trial_handler.task_id,
                "done",
                f"TIMEOUT - agent execution timed out after {timeouts.total_agent_operation} seconds (total operation including setup + execution + cleanup)"
            )

            # Try to copy logs before killing the session (for agents that support it)
            if hasattr(agent, '_copy_log_file_from_container'):
                try:
                    self._logger.info(f"Attempting to copy logs for timed-out task {trial_handler.task_id}")
                    agent._copy_log_file_from_container(session, trial_handler.agent_logging_dir)
                except Exception as log_error:
                    self._logger.warning(f"Failed to copy logs after timeout: {log_error}")

            # Kill the session immediately to stop the agent
            try:
                session.kill_session()
                self._logger.info(f"Killed agent session for timed-out task {trial_handler.task_id}")
            except Exception as e:
                self._logger.error(f"Failed to kill session after timeout: {e}")

            return None, FailureMode.AGENT_TIMEOUT

        except RetryError as e:
            last_exception = e.last_attempt.exception()
            if isinstance(last_exception, ContextLengthExceededError):
                self._logger.error(
                    f"Context length exceeded for task {trial_handler.task_id}: "
                    f"{last_exception}"
                )
                return None, FailureMode.CONTEXT_LENGTH_EXCEEDED
            elif isinstance(last_exception, ParseError):
                self._logger.error(
                    f"Failed to parse LLM response for task {trial_handler.task_id}: "
                    f"{last_exception}"
                )
                return None, FailureMode.FATAL_LLM_PARSE_ERROR

        except Exception as e:
            self._logger.error(
                f"Error running agent for task {trial_handler.task_id}: {e}"
            )
            return None, FailureMode.UNKNOWN_AGENT_ERROR

        return None, FailureMode.NONE

    # COMPREHENSIVE SETUP SCRIPT
    def _run_setup(
        self,
        terminal: Terminal,
        session: TmuxSession,
        trial_handler: TrialHandler,
        config: dict,
        file_diff_handler=None,
    ) -> FailureMode:
        """
        Run comprehensive setup including files, migration, and scripts.
        """
        import asyncio
        from .utils.timeout_manager import TimeoutManager

        # Get timeout for setup
        timeouts = TimeoutManager.get_timeouts_for_task(trial_handler.task)

        try:
            # Create setup orchestrator with terminal and session for harness-specific operations
            setup_orchestrator = SetupOrchestrator(
                logger=self._logger,
                terminal=terminal,
                session=session,
                file_diff_handler=file_diff_handler,
                trial_handler=trial_handler,
                plugin_set=self._current_plugin_set
            )

            # Run setup with timeout using asyncio
            async def run_setup():
                loop = asyncio.get_event_loop()
                task = loop.run_in_executor(
                    None,
                    setup_orchestrator.setup_task,
                    trial_handler.task_id,
                    config
                )
                return await asyncio.wait_for(task, timeout=timeouts.setup)

            # Run the async function and check result
            setup_succeeded = asyncio.run(run_setup())
            
            if not setup_succeeded:
                self._logger.error(f"Setup failed for task {trial_handler.task_id}")
                return FailureMode.SETUP_FAILED

            return FailureMode.NONE

        except asyncio.TimeoutError:
            self._logger.warning(f"Setup timed out after {timeouts.setup}s for task {trial_handler.task_id}")
            log_harness_info(
                self._logger,
                trial_handler.task_id,
                "done",
                f"TIMEOUT - task setup timed out after {timeouts.setup} seconds"
            )
            return FailureMode.SETUP_TIMEOUT
        except Exception as e:
            self._logger.error(f"Setup failed for task {trial_handler.task_id}: {e}")
            return FailureMode.SETUP_FAILED

    def _run_trial(
        self,
        trial_handler: TrialHandler,
        config: dict,
    ) -> TrialResults:
        self._logger.debug(f"Running task: {trial_handler.task_id}")

        results = TrialResults(
            trial_name=trial_handler.trial_name,
            task_id=trial_handler.task_id,
            task_prompt=trial_handler.task_prompt,
            agent=str(self._agent_name.value),
            model_name=self._model_name,
            db_type=config.get("db_type"),
            project_type=config.get("project_type"),
            plugin_set_name=self._current_plugin_set.name if self._current_plugin_set else None,
            plugin_set_skills=self._current_plugin_set.skill_locations if self._current_plugin_set else None,
            plugin_set_mcp_servers=list(self._current_plugin_set.mcp_servers.keys()) if self._current_plugin_set else None,
        )

        with spin_up_terminal(
            client_container_name=trial_handler.client_container_name,
            client_image_name=trial_handler.client_image_name,
            docker_name_prefix=trial_handler.docker_image_prefix,
            docker_compose_path=trial_handler.docker_compose_path,
            sessions_path=trial_handler.sessions_path,
            commands_path=trial_handler.commands_path,
            no_rebuild=self._no_rebuild,
            cleanup=self._cleanup,
            build_context_dir=trial_handler.input_path,
            keep_alive=self._keep_alive,
        ) as terminal:
            gitignore_path = Path(__file__).parent.parent / "shared" / "defaults" / ".gitignore"
            if gitignore_path.exists():
                self._logger.debug("Copying .gitignore to container")
                terminal.copy_to_container(
                    paths=gitignore_path,
                    container_dir="/app",
                    container_filename=".gitignore"
                )

            session = terminal.create_session(
                "agent"
            )

            # Initialize file diffing if enabled
            file_diff_handler = None
            if not self._disable_diffs:
                # Use task-level exclusions if available, otherwise use global config
                exclude_paths = (
                    trial_handler.task.file_diff_exclude_paths
                    if trial_handler.task.file_diff_exclude_paths is not None
                    else ade_bench_config.file_diff_exclude_paths
                )

                file_diff_handler = FileDiffHandler(
                    trial_handler._task_output_path,
                    enabled=True,
                    exclude_paths=exclude_paths,
                    task_name=trial_handler.task_id
                )


            #########################################################
            #########################################################
            # RUN COMPREHENSIVE SETUP SCRIPT
            try:

                setup_failure_mode = self._run_setup(terminal, session, trial_handler, config, file_diff_handler)
            except DebugBreakpointException as e:
                self._logger.info(f"Debug breakpoint hit during setup for task {trial_handler.task_id}: {e}")
                results.failure_mode = FailureMode.BREAKPOINT
                return results
            #########################################################
            #########################################################

            # If setup failed with timeout, stop the task immediately
            if setup_failure_mode == FailureMode.SETUP_TIMEOUT:
                results.failure_mode = setup_failure_mode
                self._logger.info(f"Task {trial_handler.task_id} halted due to setup timeout")
                return results
            elif setup_failure_mode != FailureMode.NONE:
                results.failure_mode = setup_failure_mode
                self._logger.warning(f"Setup failed for task {trial_handler.task_id}, halting task")
                return results

            pre_agent_pane = session.capture_pane(capture_entire=True)
            trial_handler.pre_agent_pane_path.write_text(pre_agent_pane)

            # Inject delimiter to mark the end of pre-agent phase
            session.send_keys(["echo '=== ADE_BENCH_PHASE_DELIMITER_AGENT_START ==='", "Enter"])

            # Create a fresh agent for this task
            task_agent = self._create_agent_for_task(trial_handler.task_id)

            # Set variant configuration for sage agent
            if hasattr(task_agent, 'set_variant_config'):
                task_agent.set_variant_config(config)

            log_harness_info(self._logger, trial_handler.task_id, "agent", f"Starting agent...")
            try:
                agent_result, agent_failure_mode = self._run_agent(
                    session=session,
                    agent=task_agent,
                    trial_handler=trial_handler,
                    task_name=trial_handler.task_id,
                )
            except DebugBreakpointException as e:
                self._logger.info(f"Debug breakpoint hit during agent execution for task {trial_handler.task_id}: {e}")
                results.failure_mode = FailureMode.BREAKPOINT
                return results

            # Capture the full pane and split on delimiter to get post-agent content
            full_pane = session.capture_pane(capture_entire=True)
            parts = full_pane.split('=== ADE_BENCH_PHASE_DELIMITER_AGENT_START ===')
            post_agent_pane = parts[-1].strip()

            # Only write agent.log and format it for agents with log formatters (e.g., Claude Code)
            formatted_content = None
            agent_log_path = None
            if hasattr(task_agent, '_log_formatter') and task_agent._log_formatter is not None:
                agent_log_path = trial_handler.sessions_path / "agent.log"
                try:
                    agent_log_path.write_text(post_agent_pane)
                    # Get formatted content from agent (returns string or None)
                    formatted_content = task_agent.format_agent_log(agent_log_path)
                    if formatted_content:
                        self._logger.debug(f"Generated formatted agent.txt from agent.log using agent's formatter")
                except Exception as e:
                    self._logger.warning(f"Failed to write/format agent.log: {e}. Using raw pane output.")
                    agent_log_path = None  # Mark as unavailable on error

            # Write to file - either formatted content or fallback to raw pane
            if formatted_content:
                trial_handler.agent_pane_path.write_text(formatted_content)
            else:
                trial_handler.agent_pane_path.write_text(post_agent_pane)

            # Extract tools used if log file is available
            if agent_log_path and agent_log_path.exists():
                try:
                    results.tools_used = task_agent.extract_tools_used(agent_log_path)
                except Exception as e:
                    self._logger.debug(f"Could not extract tools used: {e}")

            # Capture snapshot after agent and create agent diff
            if file_diff_handler:
                file_diff_handler.handle_phase_diffing(terminal.container, "agent", trial_handler.task_id, self._logger)

            # If agent setup timed out, stop the task immediately (don't run tests)
            if agent_failure_mode == FailureMode.AGENT_SETUP_TIMEOUT:
                results.failure_mode = agent_failure_mode
                self._logger.info(f"Task {trial_handler.task_id} halted due to agent setup or installation timeout")
                log_harness_info(self._logger, trial_handler.task_id, "done", "TIMEOUT - agent setup timed out")
                # Session should be killed
                try:
                    session.kill_session()
                except Exception as e:
                    self._logger.debug(f"Session already killed or error during cleanup: {e}")
                return results

            # If agent timed out, stop the task immediately (don't run tests)
            elif agent_failure_mode == FailureMode.AGENT_TIMEOUT:
                results.failure_mode = agent_failure_mode
                self._logger.info(f"Task {trial_handler.task_id} halted due to agent execution timeout")
                # Session already killed in _run_agent, but try again to be safe
                try:
                    session.kill_session()
                except Exception as e:
                    self._logger.debug(f"Session already killed or error during cleanup: {e}")
                return results

            elif agent_failure_mode != FailureMode.NONE:
                # Any other agent failure should also halt the task
                results.failure_mode = agent_failure_mode
                self._logger.warning(f"Task {trial_handler.task_id} halted due to agent failure: {agent_failure_mode}")
                log_harness_info(self._logger, trial_handler.task_id, "done", f"ERROR - {agent_failure_mode.value}")
                # Kill the session to ensure cleanup
                try:
                    session.kill_session()
                except Exception as e:
                    self._logger.warning(f"Failed to kill agent session for task {trial_handler.task_id}: {e}")
                return results

            if agent_result is not None:
                results.input_tokens = agent_result.input_tokens
                results.output_tokens = agent_result.output_tokens
                results.cache_tokens = agent_result.cache_tokens
                results.num_turns = agent_result.num_turns
                results.runtime_ms = agent_result.runtime_ms
                results.cost_usd = agent_result.cost_usd
                # Use parsed model name if harness model_name was not explicitly specified
                if not results.model_name and agent_result.model_name:
                    results.model_name = agent_result.model_name
                    self._logger.debug(
                        f"Using model name from agent output: {agent_result.model_name}"
                    )

            # Always kill the agent session to ensure cleanup, regardless of success/failure
            try:
                session.kill_session()
            except Exception as e:
                self._logger.warning(
                    f"Failed to kill agent session for task {trial_handler.task_id}: {e}"
                )

            if not trial_handler.task.run_tests_in_same_shell:
                session = terminal.create_session(
                    "tests"
                )

            try:
                test_failure_mode = self._run_tests(
                    terminal=terminal,
                    session=session,
                    trial_handler=trial_handler,
                )
            except DebugBreakpointException as e:
                self._logger.info(f"Debug breakpoint hit during test execution for task {trial_handler.task_id}: {e}")
                results.failure_mode = FailureMode.BREAKPOINT
                return results

            post_agent_pane = session.capture_pane(capture_entire=True)
            trial_handler.post_agent_pane_path.write_text(post_agent_pane)

            # Save the complete diff log
            if file_diff_handler:
                file_diff_handler.save_diff_log()

            agent_recording_path = trial_handler.sessions_path / "agent.cast"

            results.recording_path = str(
                agent_recording_path.relative_to(self._output_path)
            )

            if agent_result is not None:
                asciinema_handler = AsciinemaHandler(
                    markers=agent_result.timestamped_markers,
                    recording_path=agent_recording_path,
                )
                asciinema_handler.merge_markers()

            # Extract CSV files if requested
            if self._create_seed:
                self._extract_csv_files(terminal, trial_handler)

            # If the test failed, but the agent didn't, use the test failure mode
            if (
                test_failure_mode != FailureMode.NONE
                and results.failure_mode == FailureMode.UNSET
            ):
                results.failure_mode = test_failure_mode
                return results

        parser_result, parse_failure_mode = self._parse_results(
            trial_handler=trial_handler,
            post_agent_pane=post_agent_pane,
        )

        if parse_failure_mode != FailureMode.NONE:
            results.failure_mode = parse_failure_mode
            return results

        # Check for panic in test output (e.g., dbt-fusion panic)
        # This is a harness failure, not a task failure
        if "panic:" in post_agent_pane.lower():
            self._logger.warning(
                f"Panic detected in test output for task {trial_handler.task_id}. "
                "This is a harness failure, not a task failure."
            )
            log_harness_info(self._logger, trial_handler.task_id, "done", "ERROR - harness_panic")
            results.failure_mode = FailureMode.HARNESS_PANIC
            return results

        results.parser_results = parser_result.test_results
        results.expected_test_count = parser_result.expected_test_count
        results.is_resolved = self._is_resolved(parser_result)

        if results.is_resolved:
            self._logger.debug(f"Resolved task {trial_handler.task_id}")
        else:
            self._logger.debug(f"Unresolved task {trial_handler.task_id}")

        return results

    def _extract_table_schema(self, con, table_name: str) -> dict:
        """Extract schema information from a database table."""
        try:
            # Use information_schema to get table schema - more robust than DESCRIBE
            schema_query = f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """
            schema_result = con.execute(schema_query).fetchall()

            columns = []
            for row in schema_result:
                col_name, col_type = row
                columns.append({
                    "name": col_name,
                    "type": col_type.lower()  # Use DuckDB type directly
                })

            return {
                "name": f"solution__{table_name}",
                "columns": columns
            }
        except Exception as e:
            self._logger.error(f"Failed to extract schema for table {table_name}: {e}")
            return None

    def _extract_csv_files(self, terminal: Terminal, trial_handler: TrialHandler) -> None:
        """Extract CSV files and schema file from the database after agent execution."""
        # Read task.yaml to get tables to extract
        task_yaml_path = trial_handler.input_path / "task.yaml"
        if not task_yaml_path.exists():
            self._logger.warning(f"task.yaml not found for {trial_handler.task_id}")
            return

        import yaml
        with open(task_yaml_path, 'r') as f:
            task_config = yaml.safe_load(f)

        # Extract table names from solution_seeds (all items are dictionaries)
        tables_to_extract = []

        solution_seeds = task_config.get('solution_seeds', [])
        for item in solution_seeds:
            if isinstance(item, dict):
                table_name = item.get('table_name')
                if table_name:
                    tables_to_extract.append(table_name)
                    # Also add alternates if present
                    alternates = item.get('alternates', [])
                    if alternates:
                        tables_to_extract.extend(alternates)
                else:
                    self._logger.warning(f"Invalid solution_seed item (missing table_name): {item}")
            else:
                self._logger.warning(f"Invalid solution_seed item type (expected dict): {type(item)}")

        if not tables_to_extract:
            log_harness_info(self._logger, trial_handler.task_id, "seed", f"No valid tables to extract")
            return

        log_harness_info(self._logger, trial_handler.task_id, "seed", f"Extracting tables: {tables_to_extract}")

        # Get the current running variant information directly from the trial handler
        variant_db_type = trial_handler.variant_config.get('db_type', '')
        variant_db_name = trial_handler.variant_config.get('db_name', '')

        if variant_db_type == 'duckdb':
            self._extract_duckdb_csv(terminal, trial_handler, variant_db_name, tables_to_extract, task_config)
        else:
            log_harness_info(self._logger, trial_handler.task_id, "seed", f"CSV extraction not supported for db_type: {variant_db_type}")

    def _extract_duckdb_csv(self, terminal: Terminal, trial_handler: TrialHandler, db_name: str, tables_to_extract: list, task_config: dict) -> None:
        """Extract CSV files from DuckDB database."""
        # Create output directory
        task_seeds_dir = trial_handler.input_path / "seeds"
        task_seeds_dir.mkdir(parents=True, exist_ok=True)

        try:
            import tempfile
            import os
            import subprocess

            # Create temp directory for database file
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_db_path = os.path.join(temp_dir, f"{db_name}.duckdb")

                # Copy database file from container using docker cp
                container_name = terminal.container.name
                db_path = f"/app/{db_name}.duckdb"

                result = subprocess.run([
                    "docker", "cp", f"{container_name}:{db_path}", temp_db_path
                ], capture_output=True, text=True)

                if result.returncode != 0:
                    self._logger.error(f"Failed to copy database: {result.stderr}")
                    return

                # Extract tables using Python
                import duckdb
                con = duckdb.connect(temp_db_path)

                # Collect all schema information
                all_schemas = []

                for table_name in tables_to_extract:
                    try:
                        # Extract schema
                        schema_info = self._extract_table_schema(con, table_name)
                        if schema_info:
                            all_schemas.append(schema_info)

                        # Extract CSV data using DuckDB's COPY command
                        csv_path = task_seeds_dir / f"solution__{table_name}.csv"
                        copy_query = f"COPY {table_name} TO '{csv_path}' (HEADER, DELIMITER ',');"
                        con.execute(copy_query)
                        log_harness_info(self._logger, trial_handler.task_id, "seed", f"Exported {table_name} to {csv_path}")
                    except Exception as e:
                        self._logger.error(f"Failed to export table {table_name}: {e}")

                # Write schema information to _no-op.txt file
                # Has to be a txt file because dbt reads yml files as config
                if all_schemas:
                    no_op_path = task_seeds_dir / "_no-op.txt"

                    # Get project name from current variant
                    project_name = trial_handler.variant_config.get('project_name', 'default')

                    # Create the seeds section in proper YAML format
                    seeds_content = {
                        'seeds': {
                            project_name: {}
                        }
                    }

                    # Add column types for each table
                    for schema in all_schemas:
                        table_name = schema['name']
                        column_types = {}
                        for col in schema['columns']:
                            # Convert hugeint to bigint for Snowflake compatibility
                            col_type = col['type']
                            if col_type.lower() == 'hugeint':
                                col_type = 'bigint'
                            column_types[col['name']] = col_type

                        seeds_content['seeds'][project_name][table_name] = {
                            '+column_types': column_types
                        }

                    import yaml
                    with open(no_op_path, 'w') as f:
                        f.write('\n\n')  # Add two blank lines at the start
                        yaml.dump(seeds_content, f, default_flow_style=False, sort_keys=False)

                    log_harness_info(self._logger, trial_handler.task_id, "seed", f"Generated _no-op.txt file: {no_op_path}")

                con.close()

        except Exception as e:
            self._logger.error(f"Failed to extract tables for {trial_handler.task_id}: {e}")

    def _write_results(self, results: BenchmarkResults) -> None:
        self._results_output_path.write_text(results.model_dump_json(indent=4))

        # Also write TSV
        tsv_path = self._run_path / "results.tsv"
        write_results_tsv(results, tsv_path, self._run_id)

    def _get_git_commit_hash(self) -> str:
        """Get the current git commit hash."""
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
                )
                .decode("utf-8")
                .strip()
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return "unknown"

    def _get_user(self) -> str:
        """Get the user who ran the experiment.

        First tries to get the git user.name, falls back to system username.
        """
        try:
            git_user = (
                subprocess.check_output(
                    ["git", "config", "user.name"], stderr=subprocess.DEVNULL
                )
                .decode("utf-8")
                .strip()
            )
            if git_user:
                return git_user
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        try:
            return (
                subprocess.check_output(["whoami"], stderr=subprocess.DEVNULL)
                .decode("utf-8")
                .strip()
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return "unknown"

    def _upload_results_to_s3(self) -> None:
        """Upload entire run directory to S3 bucket."""
        files_to_upload = [f for f in self._run_path.rglob("*") if f.is_file()]

        if not files_to_upload:
            self._logger.warning(f"No files found to upload in {self._run_path}")
            return

        try:
            s3_client = boto3.client("s3")
            log_harness_info(self._logger, "system", "upload", f"Uploading run results to S3 bucket: {self._s3_bucket}")

            failed_uploads = []

            for file_path in files_to_upload:
                relative_path = file_path.relative_to(self._run_path)
                s3_key = f"{self._run_id}/{relative_path}"

                try:
                    self._logger.debug(
                        f"Uploading {relative_path} to s3://{self._s3_bucket}/{s3_key}"
                    )
                    s3_client.upload_file(str(file_path), self._s3_bucket, s3_key)
                except Exception as file_error:
                    self._logger.warning(
                        f"Failed to upload {relative_path}: {file_error}"
                    )
                    failed_uploads.append(str(relative_path))

            if not failed_uploads:
                log_harness_info(
                    self._logger,
                    "system",
                    "upload",
                    f"Successfully uploaded all {len(files_to_upload)} files to "
                    f"s3://{self._s3_bucket}/{self._run_id}/"
                )
            else:
                self._logger.warning(
                    f"Uploaded {len(files_to_upload) - len(failed_uploads)} of "
                    f"{len(files_to_upload)} files. "
                    f"{len(failed_uploads)} files failed to upload."
                )
                self._logger.warning(
                    f"Failed files: {', '.join(failed_uploads[:5])}"
                    + ("..." if len(failed_uploads) > 5 else "")
                )

        except Exception as e:
            self._logger.error(f"Failed to upload {self._run_path} results to S3: {e}")

    def _write_run_metadata(self) -> None:
        metadata = RunMetadata(
            run_id=self._run_id,
            dataset_path=str(self._dataset_path.absolute()),
            output_path=str(self._output_path.absolute()),
            agent_name=self._agent_name.value,
            no_rebuild=self._no_rebuild,
            cleanup=self._cleanup,
            log_level=self._log_level,
            task_ids=self._dataset.task_ids,
            exclude_task_ids=self._exclude_task_ids,
            n_concurrent_trials=self._n_concurrent_trials,
            n_attempts=self._n_attempts,
            max_episodes=self._max_episodes,
            dataset_size=len(self._dataset),
            model_name=self._model_name,
            commit_hash=self._get_git_commit_hash(),
            username=self._get_user(),
            start_time=self._start_time,
            s3_bucket=self._s3_bucket if self._s3_bucket else None,
        )
        self._run_uuid = metadata.uuid

        self._run_metadata_output_path.write_text(metadata.model_dump_json(indent=4))

    def _update_metadata_on_end(self, results: BenchmarkResults) -> None:
        metadata = RunMetadata.model_validate_json(
            self._run_metadata_output_path.read_text()
        )
        metadata.end_time = datetime.now(timezone.utc).isoformat()
        metadata.accuracy = results.accuracy
        metadata.pass_at_k = results.pass_at_k
        self._run_metadata_output_path.write_text(metadata.model_dump_json(indent=4))

    def _execute_single_trial(
        self,
        trial_name: str,
        task_path: Path,
        task_key: str,
        config: dict,
    ) -> TrialResults:
        """Execute a single task and return its results.

        Args:
            task_path: Path to the task directory
            task_key: Optional key for the specific task config
            config: Optional database/project configuration dict

        Returns:
            TrialResults: The results of the trial execution
        """
        trial_handler = TrialHandler(
            trial_name=trial_name,
            input_path=task_path,
            output_path=self._run_path,
            task_key=task_key,
            variant_config=config,
            agent_name=self._agent_name,
        )

        try:
            trial_results = self._run_trial(trial_handler, config)

            trial_handler.results_path.write_text(
                trial_results.model_dump_json(indent=4)
            )

            return trial_results

        except Exception as e:
            logger.error(
                f"Harness execution failed for {task_path} with key {task_key}: {e}"
            )
            # Update logger table
            log_harness_info(logger, trial_handler.task_id, "done", f"ERROR - {e}")

            trial_results = TrialResults(
                trial_name=trial_name,
                task_id=trial_handler.task_id,
                task_prompt=trial_handler.task_prompt,
                failure_mode=FailureMode.UNKNOWN_HARNESS_ERROR,
                agent=str(self._agent_name.value),
                model_name=self._model_name,
                db_type=config.get("db_type"),
                project_type=config.get("project_type"),
                plugin_set_name=self._current_plugin_set.name if self._current_plugin_set else None,
                plugin_set_skills=self._current_plugin_set.skill_locations if self._current_plugin_set else None,
                plugin_set_mcp_servers=list(self._current_plugin_set.mcp_servers.keys()) if self._current_plugin_set else None,
            )
            return trial_results

    def _get_trial_name(
        self,
        task_path: Path,
        task_key: str | None,
        attempt: int,
    ) -> str:
        if task_key is None:
            return f"{task_path.name}.{attempt}-of-{self._n_attempts}"
        return f"{task_path.name}.{task_key}.{attempt}-of-{self._n_attempts}"

    def _execute_tasks(self) -> BenchmarkResults:
        """Execute all tasks in parallel and collect their results."""
        results = BenchmarkResults()

        # Get tasks that have matching database and project type
        all_tasks = self._dataset
        matching_tasks = []
        task_ids = []

        for task_path, task_key in all_tasks:
            trial_handler = TrialHandler(
                trial_name="temp",
                input_path=task_path,
                task_key=task_key,
            )
            variants = [config.model_dump() for config in trial_handler.task.variants]

            # Find the matching config
            matching_config = None
            for variant in variants:
                if variant.get("db_type") == self._db_filter and variant.get("project_type") == self._project_type_filter:
                    matching_config = variant
                    break

            if matching_config:
                matching_tasks.append((task_path, task_key, matching_config))
                task_ids.append(trial_handler.task_id)

        # Log filtering summary
        total_tasks = len(self._dataset)
        matching_count = len(matching_tasks)
        log_harness_info(self._logger, "system", "start", f"Running with {self._db_filter} + {self._project_type_filter}. Found {matching_count} tasks of {total_tasks} requested tasks.")

        if not matching_tasks:
            self._logger.warning("No tasks have matching database and project type configurations")
            return results

        # Initialize dynamic logging with task IDs (only if dynamic logging is enabled)
        if ade_bench_config.use_dynamic_logging:
            initialize_dynamic_logging(task_ids)

        # Calculate total number of tasks (matching tasks * attempts)
        total_tasks = len(matching_tasks) * self._n_attempts
        max_workers = min(total_tasks, self._n_concurrent_trials)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # For each matching task and attempt, create a future
            future_to_task = {}
            for task_path, task_key, config in matching_tasks:
                for attempt in range(1, self._n_attempts + 1):
                    trial_name = self._get_trial_name(task_path, task_key, attempt)
                    future = executor.submit(
                        self._execute_single_trial,
                        trial_name=trial_name,
                        task_path=task_path,
                        task_key=task_key,
                        config=config,
                    )
                    future_to_task[future] = (trial_name, attempt, config)

            # Track progress
            completed_tasks = 0

            for future in as_completed(future_to_task):
                trial_name, attempt, config = future_to_task[future]
                trial_results = future.result()
                results.results.append(trial_results)
                completed_tasks += 1

                self._write_results(results)

                # Log progress update
                successful_tasks = sum(1 for result in results.results if result.is_resolved)
                percentage = (successful_tasks / completed_tasks * 100) if completed_tasks > 0 else 0
                log_harness_info(
                    self._logger,
                    "SUMMARY",
                    "",
                    f"Run {completed_tasks} of {total_tasks} tasks, {successful_tasks} successful ({percentage:.1f}%)"
                )

        return results

    def run(self) -> BenchmarkResults:
        """Run the benchmark with all configured plugin sets."""
        all_results = BenchmarkResults()
        original_run_id = self._run_id

        for plugin_set in self._plugin_sets:
            # Create run ID with plugin set suffix
            self._run_id = f"{original_run_id}__{plugin_set.name}"
            self._current_plugin_set = plugin_set

            # Ensure output directory exists for this plugin set
            self._run_path.mkdir(parents=True, exist_ok=True)

            # Initialize file logger for this plugin set's run path
            self._init_file_logger()

            self._logger.info(f"Starting run for plugin set: {plugin_set.name}")

            # Run trials for this plugin set
            results = self._execute_trials()
            all_results.results.extend(results.results)

        self._run_id = original_run_id
        return all_results

    def _execute_trials(self) -> BenchmarkResults:
        """Execute trials for the current skill set.

        Returns:
            BenchmarkResults: The results of the trials.
        """
        log_harness_info(logger, "system", "start", "STARTING HARNESS RUN")
        log_harness_info(logger, "system", "start", f"Run ID: {self._run_id}")

        profiler = cProfile.Profile()
        start_time = None

        if self._with_profiling:
            self.profiler_output_path.mkdir(parents=True, exist_ok=True)
            profiler.enable()
            start_time = time.perf_counter()

        self._write_run_metadata()
        results = self._execute_tasks()
        self._update_metadata_on_end(results=results)

        if self._with_profiling:
            profiler.disable()
            execution_time = time.perf_counter() - start_time
            profiler.dump_stats(self._cProfile_output_path)

            profiling_metadata = {
                "execution_time_seconds": execution_time,
                "n_concurrent_trials": self._n_concurrent_trials,
                "disable_diffs": self._disable_diffs,
                "agent_name": self._agent_name.value,
            }

            with open(self._profiler_metadata_output_path, "w") as f:
                json.dump(profiling_metadata, f, indent=4)

        # Stop the Rich logger (only if dynamic logging is enabled)
        if ade_bench_config.use_dynamic_logging:
            rich_logger.stop()


        # Generate HTML results dashboard
        if not self._disable_diffs:
            try:
                from scripts_python.generate_results_html import ResultsHTMLGenerator
                generator = ResultsHTMLGenerator(self._run_path)
                generator.generate_all()
                log_harness_info(self._logger, "system", "finish", "Generated HTML dashboard.")
            except Exception as e:
                log_harness_info(self._logger, "system", "finish", "Failed to generate HTML dashboard.")

        # Log harness completion
        successful_tasks = sum(1 for result in results.results if result.is_resolved)
        total_tasks = len(results.results)
        log_harness_info(
            self._logger,
            "system",
            "finish",
            f"Harness run completed: {successful_tasks} of {total_tasks} tasks successful"
        )

        if self._with_profiling:
            log_harness_info(
                self._logger,
                "system",
                "finish",
                f"Profiling informationn from cProfiler saved to {self._cProfile_output_path}."
            )

        return results
