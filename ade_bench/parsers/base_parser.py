from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from ade_bench.utils.logger import logger


class UnitTestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass
class ParserResult:
    """Result from parsing test output, containing both test results and status messages."""

    test_results: dict[str, UnitTestStatus]
    status_message: Optional[str] = None
    expected_test_count: Optional[int] = (
        None  # Number of tests expected (from "[ade-bench] expected_test_count=N" line)
    )


class BaseParser(ABC):
    def __init__(self, task_name: str = "unknown") -> None:
        self._logger = logger.getChild(__name__)
        self._task_name = task_name

    @abstractmethod
    def parse(self, content: str) -> ParserResult:
        pass
