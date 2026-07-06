# key — non-blocking single-key input
from __future__ import annotations

import sys
import select
import time

try:
    import termios
    import tty
    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False

from .config import console


def get_key(timeout: float = 0.5) -> str | None:
    """Read single key without Enter. Returns key or None on timeout."""
    if sys.platform == 'win32':
        import msvcrt
        if msvcrt.kbhit():
            return msvcrt.getch().decode(errors='replace').lower()
        if timeout:
            time.sleep(timeout)
        return None
    if _HAS_TERMIOS:
        fd = sys.stdin.fileno()
        if select.select([sys.stdin], [], [], timeout)[0]:
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            if ch in ('\r', '\n', '\x03', '\x04'):
                return None
            return ch.lower()
        return None
    # fallback: blocking read (no auto-advance)
    console.print('\n 命令: ', end='')
    try:
        line = input().strip().lower()
        return line[:1] if line else None
    except (EOFError, KeyboardInterrupt):
        return None
