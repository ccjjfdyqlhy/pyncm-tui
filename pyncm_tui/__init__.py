# pyncm_tui — Rich-based interactive frontend for Netease Cloud Music
# Usage: python -m pyncm_tui

from pyncm import setNewSession

from .config import console, SESSION_FILE
from .queue import queue
from .session import login_screen
from .menu import main_menu
from .helpers import clear_screen
from rich.prompt import Prompt, Confirm

# ── 用户按 Enter 提交 → 自动清屏 ──
_orig_prompt_ask = Prompt.ask
def _prompt_ask_clear(*a, **k):
    r = _orig_prompt_ask(*a, **k)
    clear_screen()
    return r
Prompt.ask = _prompt_ask_clear

_orig_confirm_ask = Confirm.ask
def _confirm_ask_clear(*a, **k):
    r = _orig_confirm_ask(*a, **k)
    clear_screen()
    return r
Confirm.ask = _confirm_ask_clear

import os


def main():
    logged_in = login_screen()
    if not logged_in:
        console.print()
        console.print('[yellow] 以游客模式运行（部分功能受限）[/yellow]')
        console.print()
        console.print('[dim]  [回车] 进入主菜单[/dim]')
        Prompt.ask('', default='')

    while True:
        try:
            r = main_menu()
            if r == 'logout':
                if os.path.exists(SESSION_FILE):
                    os.remove(SESSION_FILE)
                setNewSession()
                queue.clear()
                logged_in = login_screen()
                if not logged_in:
                    console.print()
                    console.print('[yellow] 以游客模式运行[/yellow]')
                    console.print()
                    console.print('[dim]  [回车] 进入主菜单[/dim]')
                    Prompt.ask('', default='')
        except KeyboardInterrupt:
            console.print()
            console.print('[yellow]再见~[/yellow]')
            break
        except Exception as e:
            console.print(f'[red]错误: {e}[/red]')
            console.print('[dim]  [回车] 继续[/dim]')
            Prompt.ask('', default='')


if __name__ == '__main__':
    main()
