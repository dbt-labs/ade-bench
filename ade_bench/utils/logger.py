import logging
import sys
import threading
from datetime import datetime
from typing import Optional, Dict
from rich.console import Console
from rich.table import Table
from rich.live import Live

from ade_bench.config import config


class RichTaskLogger:
    """Rich-based logger that shows one row per task with live updates."""

    def __init__(self):
        self._lock = threading.Lock()
        self._console = Console()
        self._table = None
        self._live = None
        self._task_data: Dict[str, Dict[str, str]] = {}  # task_id -> {stage, message, timestamp}
        self._initialized = False
        self._original_console_handlers = []  # Store original console handlers

    def initialize_tasks(self, task_ids: list[str]) -> None:
        """Initialize the Rich table with task rows."""
        with self._lock:
            if self._initialized:
                return

            # Initialize task data
            for task_id in task_ids:
                self._task_data[task_id] = {"stage": "", "message": "Waiting...", "timestamp": ""}

            # Add summary row as a regular task
            self._task_data["SUMMARY"] = {"stage": "", "message": "Waiting...", "timestamp": ""}

            # Create initial table
            self._table = self._create_table()

            # Start live display
            self._live = Live(self._table, console=self._console, refresh_per_second=4)
            self._live.start()
            self._initialized = True

    def _disable_console_handlers(self) -> None:
        """Disable console handlers to prevent double printing."""
        # Get all existing loggers
        all_loggers = [logging.getLogger(name) for name in logging.Logger.manager.loggerDict]
        all_loggers.append(logging.getLogger())  # Add root logger

        # Find and store console handlers (both stdout and stderr)
        for logger_obj in all_loggers:
            for handler in logger_obj.handlers[:]:
                if isinstance(handler, logging.StreamHandler) and handler.stream in (
                    sys.stdout,
                    sys.stderr,
                ):
                    self._original_console_handlers.append((logger_obj, handler))
                    logger_obj.removeHandler(handler)

    def update_task_from_dict(self, log_data: dict) -> None:
        """Update a specific task's row from log data dictionary."""
        with self._lock:
            task_id = log_data["task"]

            if not self._initialized:
                # Use the message formatter for consistency
                log_line = format_log_line(log_data)
                print(log_line, flush=True)
                return

            # Update task data
            if task_id not in self._task_data:
                # Use the message formatter for consistency
                log_line = format_log_line(log_data)
                print(log_line, flush=True)
                return

            self._task_data[task_id] = {
                "stage": log_data["formatted_stage"],
                "message": log_data["formatted_message"],
                "timestamp": log_data["formatted_timestamp"],
            }

            # Rebuild table with updated data
            self._rebuild_table()

    def _create_table(self) -> Table:
        """Create a new table with current task data."""
        # Create table with fixed column widths
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim", width=8, no_wrap=True)
        table.add_column("Task", style="cyan", width=32, no_wrap=True)
        table.add_column("Stage", style="green", width=12, no_wrap=True)
        table.add_column("Message", style="white", width=100, no_wrap=True)

        # Add rows for each task (excluding SUMMARY)
        for task_id, data in self._task_data.items():
            if task_id != "SUMMARY":  # Skip SUMMARY - it gets added separately
                table.add_row(data["timestamp"], task_id, data["stage"], data["message"])

        # Add divider row
        table.add_row("─" * 8, "─" * 32, "─" * 12, "─" * 100)

        # Add summary row (if it exists in task data)
        if "SUMMARY" in self._task_data:
            summary_data = self._task_data["SUMMARY"]
            table.add_row(
                summary_data["timestamp"], "SUMMARY", summary_data["stage"], summary_data["message"]
            )

        return table

    def _rebuild_table(self) -> None:
        """Rebuild the table with current task data."""
        if not self._live:
            return

        # Create new table and update live display
        new_table = self._create_table()
        self._live.update(new_table)

    def stop(self) -> None:
        """Stop the live display and re-enable console handlers."""
        with self._lock:
            if self._live:
                self._live.stop()
                self._initialized = False

            # Re-enable console handlers
            for logger_obj, handler in self._original_console_handlers:
                logger_obj.addHandler(handler)
            self._original_console_handlers.clear()


# Global instance
rich_logger = RichTaskLogger()


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger


def format_log_message(message: str) -> str:
    """Format message with truncation to 97 characters."""
    if len(message) > 100:
        return message[:97] + "..."
    return message


def format_log_stage(stage: str) -> str:
    """Format the stage name for display."""
    prefixes = {
        "SETUP": "* · ·  ",
        "AGENT": "✓ * ·  ",
        "EVAL": "✓ ✓ *  ",
        "SEED": "✓ ✓ ⤴  ",
        "DONE": "✓ ✓ ✓  ",
    }

    stage_upper = stage.upper()
    if stage_upper in prefixes:
        return prefixes[stage_upper] + stage_upper
    else:
        return stage_upper


def format_log_timestamp(timestamp: datetime) -> str:
    """Format timestamp for display."""
    return timestamp.strftime("%H:%M:%S")


def format_log_line(log_data: dict) -> str:
    return f"{log_data['formatted_timestamp']:<8} | {log_data['task']:<32} | {log_data['formatted_stage']:<12} | {log_data['formatted_message']}"


def log(
    logger: logging.Logger,
    task: str,
    stage: str,
    message: str,
    timestamp: Optional[datetime] = None,
) -> None:
    """
    Centralized info logging function for the harness.

    Args:
        logger: The logger instance to use
        task: The task being run
        stage: The task stage (setup, agent run, test, cleanup)
        message: The log message
        timestamp: Optional timestamp, defaults to current time
    """
    if timestamp is None:
        timestamp = datetime.now()

    # Step 1: Create log data dictionary
    log_data = {"task": task, "stage": stage, "message": message, "timestamp": timestamp}

    # Step 2: Add formatted components to the dict
    log_data["formatted_message"] = format_log_message(message)
    log_data["formatted_stage"] = format_log_stage(stage)
    log_data["formatted_timestamp"] = format_log_timestamp(timestamp)

    # Step 3: Create log line string from dict
    log_line = format_log_line(log_data)

    # Step 4: Record in saved logs (always happens)
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    if file_handlers:
        file_handler = file_handlers[0]
        record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=log_line,
            args=(),
            exc_info=None,
        )
        file_handler.emit(record)

    # Step 5 & 6: Console output based on config and log type
    if config.use_dynamic_logging:
        # Rich logs on - route based on log category
        if task.upper() == "SYSTEM":
            # System logs - just print (harness starting, done, etc.)
            print(log_line, flush=True)
        else:
            rich_logger.update_task_from_dict(log_data)
    else:
        # Rich logs off - print log line to console
        print(log_line, flush=True)


def log_harness_info(
    logger: logging.Logger,
    task: str,
    stage: str,
    message: str,
    timestamp: Optional[datetime] = None,
) -> None:

    try:
        log(logger, task, stage, message, timestamp)
    except Exception as e:
        # Fallback to simple print if logging fails
        print(f"Logging error: {e}", flush=True)
        print(f"Original message: {task} | {stage} | {message}", flush=True)


def initialize_dynamic_logging(task_ids: list[str]) -> None:
    """Initialize the Rich logging system with the list of tasks."""
    # Disable console handlers to prevent double printing
    rich_logger._disable_console_handlers()

    # Initialize the Rich table with tasks
    rich_logger.initialize_tasks(task_ids)

    # Give a moment for the table to initialize
    import time

    time.sleep(0.5)


logger = setup_logger(__name__)
