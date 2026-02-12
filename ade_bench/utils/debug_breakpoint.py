"""
Debug breakpoint functionality for halting task execution.
"""


class DebugBreakpointException(Exception):
    """Exception raised when a debug breakpoint is hit."""

    pass


def breakpoint(message: str = "", logger=None):
    """
    Debug breakpoint that cleanly halts task execution.

    Args:
        message: Optional message to display before halting
        logger: Optional logger to use for output
    """
    if logger:
        logger.info(f"🔴 DEBUG BREAKPOINT: {message}")
    else:
        print(f"🔴 DEBUG BREAKPOINT: {message}")

    # Raise exception to halt execution cleanly
    raise DebugBreakpointException(f"Debug breakpoint hit: {message}")
