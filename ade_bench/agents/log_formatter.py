"""
Agent log formatting utilities.

This module provides utilities for parsing and formatting agent log files
into human-readable text. Each agent can implement its own log formatter
by subclassing LogFormatter.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class LogFormatter(ABC):
    """Base class for agent log formatters."""

    @abstractmethod
    def parse_log_file(self, log_path: Path) -> List[Dict[str, Any]]:
        """
        Parse the agent log file and extract structured information.

        Args:
            log_path: Path to the log file to parse

        Returns:
            List of turn dictionaries containing structured log data
        """
        pass

    @abstractmethod
    def format_readable_log(self, turns: List[Dict[str, Any]]) -> str:
        """
        Format the parsed turns into a readable text string.

        Args:
            turns: List of turn dictionaries from parse_log_file

        Returns:
            Formatted log content as a string
        """
        pass

    def format_log(self, log_path: Path) -> str | None:
        """
        Parse and format a log file in one step.

        Args:
            log_path: Path to the log file to parse

        Returns:
            Formatted log content as a string, or None if formatting failed
        """
        try:
            turns = self.parse_log_file(log_path)
            if not turns:
                return None
            return self.format_readable_log(turns)
        except Exception:
            return None
