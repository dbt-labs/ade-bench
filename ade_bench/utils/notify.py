"""Terminal notification support for when ADE runs complete."""

import os
import sys


def send_terminal_notification(message: str) -> None:
    """Send a terminal notification when a run completes.

    Uses OSC 9 (iTerm2/Windows Terminal) and OSC 777 (Gnome Terminal/VTE)
    for desktop notifications, plus a BEL character as a fallback for
    terminals that support audible/visible bells.

    Writes directly to /dev/tty to bypass any stdout/stderr redirection.
    """
    # OSC 9: iTerm2, Windows Terminal, ConEmu
    osc9 = f"\x1b]9;{message}\x07"
    # OSC 777: VTE-based terminals (GNOME Terminal, Tilix, etc.)
    osc777 = f"\x1b]777;notify;ADE-bench;{message}\x07"
    # BEL: universal fallback for terminal bell
    bel = "\x07"

    payload = osc9 + osc777 + bel

    try:
        # Write to /dev/tty to bypass redirected stdout
        fd = os.open("/dev/tty", os.O_WRONLY)
        os.write(fd, payload.encode())
        os.close(fd)
    except OSError:
        # No controlling terminal (e.g., running in CI) — write to stderr
        try:
            sys.stderr.write(payload)
            sys.stderr.flush()
        except Exception:
            pass
