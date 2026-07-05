# session — save/load/login

import os
import time

from pyncm import apis, dumpSessionAsString, getCurrentSession, loadSessionFromString, setCurrentSession

from .config import console, SESSION_FILE
from rich.prompt import Prompt


def save_session():
    with open(SESSION_FILE, 'w') as f:
        f.write(dumpSessionAsString(getCurrentSession()))
    console.print('[green] 登录态已保存[/green]')


def load_session() -> bool:
    if not os.path.exists(SESSION_FILE):
        return False
    with open(SESSION_FILE) as f:
        setCurrentSession(loadSessionFromString(f.read().strip()))
    return True


def login_screen() -> bool:
    console.clear()
    console.rule('[bold cyan]登录[/bold cyan]')
    console.print()

    if load_session():
        with console.status('[yellow]检查登录态...'):
            try:
                r = apis.login.getCurrentLoginStatus()
                if r.get('code') == 200 and r.get('account'):
                    console.print('[green] 登录态恢复成功[/green]')
                    return True
            except Exception:
                pass
        console.print('[red] 登录态已过期[/red]\n')

    console.print('[yellow]使用 Cookie 登录:[/yellow]')
    console.print('  1. 浏览器打开 https://music.163.com 并登录')
    console.print('  2. F12 → Application → Cookies → music.163.com')
    console.print('  3. 复制 [bold]MUSIC_U[/bold] 的值')
    console.print()

    console.print('[dim]  [MUSIC_U] 输入Cookie  [回车] 取消[/dim]')
    music_u = Prompt.ask('[bold]MUSIC_U[/bold]', default='')
    if not music_u:
        console.print('[red]已取消[/red]')
        return False

    with console.status('[yellow]登录中...'):
        try:
            r = apis.login.loginViaCookie(MUSIC_U=music_u)
            if r.get('code') == 200:
                console.print(f'[green] 登录成功！[/green]')
                save_session()
                return True
            console.print(f'[red] 登录失败: {r}[/red]')
            return False
        except Exception as e:
            console.print(f'[red] 登录异常: {e}[/red]')
            return False
