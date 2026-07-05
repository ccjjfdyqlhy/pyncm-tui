# menu — main menu screen

from pyncm import getCurrentSession
from rich.prompt import Prompt

from .config import console
from .helpers import fmt_dur, song_artists
from .player import player
from .queue import queue


def _now_playing_indicator() -> str:
    if not player.current_song:
        return ''
    s = player.current_song
    icon = '⏸' if player.paused else '▶' if player.playing else ''
    if not icon:
        return ''
    qinfo = f'  [dim]{queue.position_str}[/dim]' if queue.songs else ''
    return (f'  {icon} [cyan]{s["name"]}[/cyan] — [green]'
            f'{song_artists(s)}[/green]'
            f' [dim]{fmt_dur(s.get("duration", s.get("dt", 0)))}[/dim]{qinfo}')


def main_menu() -> str | None:
    console.clear()

    s = getCurrentSession()
    user_line = f'[green]{s.nickname}[/green]  UID: {s.uid}' if s.logged_in else '[red]未登录[/red]'

    console.rule(f'[bold cyan]pyncm TUI[/bold cyan]')
    console.print()
    console.print(f'  [dim]用户:[/dim] {user_line}')

    np = _now_playing_indicator()
    if np:
        console.print(f'  [dim]播放:[/dim]{np}')
    if queue.songs and not player.playing and not player.paused:
        console.print(f'  [dim]队列:[/dim] {len(queue.songs)} 首 | {queue.mode_icon} {queue.mode_name_cn}')

    console.print()
    console.print('  [1] 搜索音乐')
    console.print('  [2] 我的歌单')
    console.print('  [3] 每日推荐')
    console.print('  [4] 歌词查询')
    console.print('  [5] 每日签到')
    console.print('  [6] 用户信息')
    console.print('  [7] 切换账号')
    if player.playing or player.paused:
        console.print('  [n] 播放控制')
    if queue.songs and not player.playing and not player.paused:
        console.print('  [q] 播放队列')
    console.print('  [?] 帮助')
    console.print('  [x] 退出')
    console.print()

    choices = ['1', '2', '3', '4', '5', '6', '7', '?', 'x']
    if player.playing or player.paused:
        choices.append('n')
    if queue.songs and not player.playing and not player.paused:
        choices.append('q')
    console.print(f'[dim]  输入 [{"|".join(choices)}] 选择功能[/dim]')
    choice = Prompt.ask('选择', default='x', choices=choices)

    # lazy imports to avoid circular dependency at module level
    if choice == '1':
        from .screens import search_screen
        search_screen()
    elif choice == '2':
        from .screens import my_playlists_screen
        my_playlists_screen()
    elif choice == '3':
        from .screens import daily_recommend_screen
        daily_recommend_screen()
    elif choice == '4':
        from .screens import lyrics_screen
        lyrics_screen()
    elif choice == '5':
        from .screens import signin_screen
        signin_screen()
    elif choice == '6':
        from .screens import user_profile_screen
        user_profile_screen()
    elif choice == '7':
        return 'logout'
    elif choice == '?':
        from .actions import show_help
        show_help()
    elif choice == 'n' and (player.playing or player.paused):
        from .actions import resume_playback_control
        resume_playback_control()
    elif choice == 'q' and queue.songs:
        with console.status('[yellow]缓冲中...'):
            from .engine import playback_loop
            playback_loop()
    return None
