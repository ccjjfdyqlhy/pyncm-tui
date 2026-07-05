# actions — song menu, queue screen, batch play

import time

from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

from .config import console, MAX_DISPLAY
from .helpers import fmt_dur, song_artists, song_album, song_dt, paged_slice
from .player import player
from .queue import queue


# ── batch play ──────────────────────────────────────────────────────────────

def playlist_play_all(songs: list):
    """顺序播放全部歌曲"""
    if not songs:
        console.print('[yellow] 无歌曲可播放[/yellow]')
        time.sleep(0.8)
        return
    queue.songs = list(songs)
    queue._index = 0
    queue.mode = 'sequential'
    with console.status(f'[yellow]准备播放 {len(songs)} 首...'):
        time.sleep(0.3)
    from .engine import playback_loop
    playback_loop()


def play_all_with_download(songs: list):
    """边下载边顺序播放全部歌曲"""
    if not songs:
        console.print('[yellow] 无歌曲可下载/播放[/yellow]')
        time.sleep(0.8)
        return

    from rich.prompt import Prompt as RP
    console.print('\n[bold]选择下载品质:[/bold]')
    from .config import QUALITY_MAP
    for k, (_, desc) in QUALITY_MAP.items():
        console.print(f'  [{k}] {desc}')
    q = RP.ask('品质', choices=list(QUALITY_MAP.keys()), default='2')
    level, qdesc = QUALITY_MAP[q]
    console.print(f'[green] 开始边下载边播放 {len(songs)} 首 ({qdesc})...[/green]')

    queue.songs = list(songs)
    queue._index = 0
    queue.mode = 'sequential'

    from .engine import playback_loop_with_download
    playback_loop_with_download(level)


# ── queue screen ────────────────────────────────────────────────────────────

def queue_screen():
    """查看/管理播放队列"""
    while True:
        console.clear()
        console.rule('[bold cyan]播放队列[/bold cyan]')
        console.print()

        if not queue.songs:
            console.print('[yellow] 队列为空[/yellow]')
            console.print()
            console.print('[dim]  [回车] 返回[/dim]')
            Prompt.ask('', default='')
            return

        mode_icon = queue.mode_icon
        mode_cn = queue.mode_name_cn
        total = len(queue.songs)
        console.print(f'[dim]模式: {mode_icon} {mode_cn}  |  共 {total} 首[/dim]')
        console.print()

        page = 0
        pages = (total + MAX_DISPLAY - 1) // MAX_DISPLAY

        while True:
            start, end, pages = paged_slice(total, page)
            display = queue.songs[start:end]

            console.clear()
            console.rule('[bold cyan]播放队列[/bold cyan]')
            console.print()
            console.print(f'[dim]模式: {mode_icon} {mode_cn}  |  共 {total} 首[/dim]')
            console.print()

            tbl = Table(box=None, padding=(0, 2))
            tbl.add_column('#', style='dim', width=3)
            tbl.add_column('歌名', style='cyan')
            tbl.add_column('歌手', style='green')
            tbl.add_column('时长', style='dim')
            tbl.add_column('', width=2)

            for i, s in enumerate(display):
                idx = start + i
                marker = '▶' if idx == queue._index else ''
                tbl.add_row(str(idx + 1), s['name'], song_artists(s),
                             fmt_dur(song_dt(s)), marker)
            console.print(tbl)
            console.print()

            if pages > 1:
                console.print(f'[dim]  第 {page+1}/{pages} 页 (共 {total} 首)[/dim]')

            cmds = []
            if pages > 1:
                if page > 0:
                    cmds.append('[b]上页')
                if page < pages - 1:
                    cmds.append('[n]下页')
            cmds.append('[序号]播放')
            cmds.append('[r+序号]移除')
            cmds.append('[m]切模式')
            cmds.append('[c]清空')
            cmds.append('[q]返回')
            console.print('  ' + escape('  '.join(cmds)))
            console.print()

            cmd = Prompt.ask('', default='q').strip().lower()
            if cmd == 'q':
                return
            elif cmd == 'n' and page < pages - 1:
                page += 1
                continue
            elif cmd == 'b' and page > 0:
                page -= 1
                continue
            elif cmd == 'm':
                queue.toggle_mode()
                mode_icon = queue.mode_icon
                mode_cn = queue.mode_name_cn
                continue
            elif cmd == 'c':
                queue.clear()
                player.stop()
                console.print('[green] 队列已清空[/green]')
                time.sleep(0.6)
                return
            elif cmd.startswith('r'):
                try:
                    idx = int(cmd[1:]) - 1
                    if 0 <= idx < len(queue.songs):
                        was_current = idx == queue._index
                        queue.remove(idx)
                        if was_current:
                            player.stop()
                            if queue.current:
                                console.print('[green] 已切到下一首[/green]')
                            else:
                                console.print('[yellow] 队列已空[/yellow]')
                        total = len(queue.songs)
                        if total == 0:
                            return
                        pages = (total + MAX_DISPLAY - 1) // MAX_DISPLAY
                        if page >= pages:
                            page = pages - 1
                        time.sleep(0.5)
                except (ValueError, IndexError):
                    pass
                continue
            else:
                try:
                    idx = int(cmd) - 1
                    if 0 <= idx < len(queue.songs):
                        queue.set_current(idx)
                        player.stop()
                        return
                except (ValueError, IndexError):
                    pass
            continue


# ── song action menu ────────────────────────────────────────────────────────

def song_action_menu(song: dict, subdir: str | None = None) -> bool:
    """Return True if user actioned on song, False to go back"""
    console.clear()
    console.rule('[bold cyan]歌曲操作[/bold cyan]')
    console.print()

    name = song['name']
    artists = song_artists(song)
    album = song_album(song)
    total_ms = song_dt(song)

    console.print(f'[bold]歌名:[/bold] {name}')
    console.print(f'[bold]歌手:[/bold] {artists}')
    console.print(f'[bold]专辑:[/bold] {album}')
    console.print(f'[bold]时长:[/bold] {fmt_dur(total_ms)}')
    console.print()

    p_extra = '  ⏸' if player.paused else '  ▶' if player.playing else ''
    is_current = player.current_song and player.current_song.get('id') == song['id']
    now_playing = ''
    if player.playing | player.paused:
        now_playing = f'  (当前{p_extra})' if is_current else ''
    console.print(f'  [1] [p] 播放 (替换队列){now_playing}')
    console.print(f'  [2] [a] 添加到队列')
    console.print('  [3] [d] 下载')
    console.print('  [4] [l] 歌词')
    console.print('  [5] [v] 查看队列')
    console.print('  [6] [q] 返回')
    console.print()
    console.print('[dim]  输入 1-6 或字母命令[/dim]')
    console.print()

    action = Prompt.ask('选择', default='6').lower()

    if action in ('1', 'p'):
        if is_current and (player.playing or player.paused):
            resume_playback_control()
            return True
        queue.play_now(song)
        with console.status('[yellow]缓冲中...'):
            from .engine import playback_loop
            playback_loop()
        return True
    elif action in ('2', 'a'):
        queue.add(song)
        console.print(f'[green] 已添加到队列 (共 {len(queue.songs)} 首)[/green]')
        Prompt.ask('[dim]按回车返回[/dim]', default='')
        return True
    elif action in ('3', 'd'):
        from .download import download_song
        download_song(song, subdir=subdir)
        return True
    elif action in ('4', 'l'):
        from .lyrics import show_lyrics
        show_lyrics(song['id'])
        return True
    elif action in ('5', 'v'):
        queue_screen()
        if queue.current and player.playing:
            resume_playback_control()
        elif queue.current:
            with console.status('[yellow]缓冲中...'):
                from .engine import playback_loop
                playback_loop()
        return True
    return False


def resume_playback_control():
    """回到队列播放控制"""
    if queue.current:
        from .engine import playback_loop
        playback_loop()
    elif player.current_song:
        queue.play_now(player.current_song)
        with console.status('[yellow]缓冲中...'):
            from .engine import playback_loop
            playback_loop()


# ── help ────────────────────────────────────────────────────────────────────

def show_help():
    console.clear()
    console.rule('[bold cyan]键位帮助[/bold cyan]')
    console.print()

    sections = [
        ('主菜单', [
            ('1-8', '功能选择'),
            ('n', '播放控制（有播放时）'),
            ('q', '播放队列'),
            ('?', '显示此帮助'),
            ('x', '退出'),
        ]),
        ('搜索', [
            ('1', '搜歌曲'),
            ('2', '搜专辑'),
            ('3', '搜歌手'),
            ('4', '搜歌单'),
        ]),
        ('歌曲列表页', [
            ('b', '上页（多页时）'),
            ('n', '下页（多页时）'),
            ('p', '顺序播放全部'),
            ('d', '下载全部'),
            ('pd', '下载并播放'),
            ('序号', '选曲操作（播放|添加|下载|歌词）'),
            ('回车', '返回上级'),
            ('?', '显示此帮助'),
        ]),
        ('播放队列', [
            ('序号', '播放该曲'),
            ('r+序号', '移除该曲'),
            ('m', '切换播放模式'),
            ('c', '清空队列'),
            ('q', '返回'),
        ]),
        ('歌曲操作', [
            ('1 / p', '播放（替换队列）'),
            ('2 / a', '添加到队列'),
            ('3 / d', '下载'),
            ('4 / l', '查看歌词'),
            ('5 / v', '查看队列'),
            ('6 / q', '返回'),
        ]),
    ]

    for title, items in sections:
        console.print(f'[bold cyan]{title}[/bold cyan]')
        for key, desc in items:
            console.print(f'  [green]{key:<8}[/green] {desc}')
        console.print()

    console.print('[dim]  [回车] 返回[/dim]')
    Prompt.ask('', default='')
