# lyrics — show lyrics for a song

import re

from pyncm import apis

from .config import console
from rich.prompt import Prompt
from rich.table import Table


def show_lyrics(sid: int) -> bool:
    """显示歌词。返回 True 表示成功显示。"""
    console.clear()
    console.rule('[bold cyan]歌词[/bold cyan]')
    console.print()

    with console.status('[yellow]获取歌词...'):
        try:
            lyc = apis.track.getTrackLyrics(sid)
        except Exception as e:
            console.print(f'[red] 获取失败: {e}[/red]')
            console.print()
            console.print('[dim]  [回车] 返回[/dim]')
            Prompt.ask('', default='')
            return False

    lyric_text = lyc.get('lrc', {}).get('lyric', '')
    tlyric_text = lyc.get('tlyric', {}).get('lyric', '')
    if not lyric_text:
        console.print('[yellow] 无歌词[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return False

    lines = lyric_text.split('\n')[:30]
    tlines = tlyric_text.split('\n')[:30] if tlyric_text else []

    tbl = Table(box=None, padding=(0, 2))
    tbl.add_column('歌词', style='cyan')
    if tlines:
        tbl.add_column('翻译', style='yellow')

    mx = max(len(lines), len(tlines))
    for i in range(mx):
        l = lines[i] if i < len(lines) else ''
        t = tlines[i] if i < len(tlines) else ''
        lc = re.sub(r'\[.*?\]', '', l).strip()
        tc = re.sub(r'\[.*?\]', '', t).strip()
        if lc or tc:
            tbl.add_row(lc or '', tc or '')

    console.print(tbl)
    console.print()
    console.print('[dim]  [回车] 返回[/dim]')
    Prompt.ask('', default='')
    return True
