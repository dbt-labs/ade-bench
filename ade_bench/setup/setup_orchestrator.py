"""
Simple setup orchestrator - just calls functions directly.
"""

from typing import Dict, Any
from .base_setup import setup_base_files
from .duckdb_setup import setup_duckdb
from .snowflake_setup import setup_snowflake
from .dbt_setup import setup_dbt_project
from .migration_setup import setup_migration
from .agent_setup import setup_agent_config
from ..utils.logger import log_harness_info


class SetupOrchestrator:
    """Simple orchestrator that calls setup functions directly."""

    def __init__(self, logger=None, terminal=None, session=None, file_diff_handler=None, trial_handler=None, use_skills=False):
        self.logger = logger
        self.terminal = terminal
        self.session = session
        self.file_diff_handler = file_diff_handler
        self.trial_handler = trial_handler
        self.use_skills = use_skills

    def setup_task(self, task_id: str, variant: Dict[str, Any]) -> bool:
        """Setup a task for the given variant."""
        log_harness_info(self.logger, task_id, "setup", f"Starting task setup...")


        # Set up the project
        project_type = variant.get('project_type')
        if project_type in ['dbt', 'dbt-fusion']:
            log_harness_info(self.logger, task_id, "setup", f"Setting up dbt project...")
            success, error_msg = setup_dbt_project(self.terminal, self.session, task_id, variant, self.trial_handler)
            if not success:
                log_harness_info(self.logger, task_id, "done", f"SETUP_FAILED - {error_msg}")
                return False


        # Setup agent-specific configuration files
        # Logging is in the setup_agent_config function
        setup_agent_config(self.terminal, task_id, self.trial_handler, self.logger, self.use_skills)


        # Set up the database
        db_type = variant.get('db_type')
        if db_type == 'duckdb':
            log_harness_info(self.logger, task_id, "setup", f"Setting up DuckDB database...")
            success, error_msg = setup_duckdb(self.terminal, self.session, variant, self.trial_handler)
            if not success:
                log_harness_info(self.logger, task_id, "done", f"SETUP_FAILED - {error_msg}")
                return False
        elif db_type == 'snowflake':
            log_harness_info(self.logger, task_id, "setup", f"Setting up Snowflake database from {variant.get('db_name')}...")
            success, error_msg = setup_snowflake(self.terminal, self.session, task_id, variant, self.trial_handler, self.logger)
            if not success:
                log_harness_info(self.logger, task_id, "done", f"SETUP_FAILED - {error_msg}")
                return False
            log_harness_info(self.logger, task_id, "setup", f"Snowflake setup complete.")


        # Take snapshot before migrations and main setup script
        if self.file_diff_handler:
            # Logging is contained in snapshot
            self.file_diff_handler.handle_phase_diffing(self.terminal.container, "setup", task_id, self.logger)


        # Set up any migrations and run them.
        log_harness_info(self.logger, task_id, "setup", f"Running migrations...")
        setup_migration(self.terminal, self.session, variant, self.trial_handler)
        log_harness_info(self.logger, task_id, "setup", "Migration script complete")


        # Run main setup script.
        log_harness_info(self.logger, task_id, "setup", "Running setup script...")
        setup_base_files(self.terminal, self.session, task_id, variant, self.trial_handler)
        log_harness_info(self.logger, task_id, "setup", "Setup script complete.")


        # Take final snapshot after setup script
        if self.file_diff_handler:
            # Logging is contained in snapshot
            self.file_diff_handler.handle_phase_diffing(self.terminal.container, "setup", task_id, self.logger)


        return True
