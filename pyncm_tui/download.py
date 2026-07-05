# download — download songs with quality selection

import os

import requests
from pyncm import apis
from rich.prompt import Prompt, Confirm
from rich.progress import (
    Progress, BarColumn, TextColumn, DownloadColumn,
    TransferSpeedColumn, TimeRemainingColumn,
)

from .config import console, QUALITY_MAP, MUSIC_DIR
from .helpers import safe_name, song_artists
from .engine import _find_local_file


def choose_quality_for_download() -> tuple[str, str]:
    """选择下载品质，返回 (level, description)"""
    console.print('\n[bold]选择品质:[/bold]')
    for k, (_, desc) in QUALITY_MAP.items():
        console.print(f'  [{k}] {desc}')
    q = Prompt.ask('品质', choices=list(QUALITY_MAP.keys()), default='2')
    return QUALITY_MAP[q]


def download_with_progress(url: str, filename: str, quiet: bool = False) -> bool:
    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        if not quiet:
            console.print(f'[red] 下载失败: {e}[/red]')
        return False

    total = int(resp.headers.get('content-length', 0))

    progress = Progress(
        TextColumn('[bold blue]{task.fields[name]}'),
        BarColumn(),
        TextColumn('{task.percentage:>3.0f}%'),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task(
            'download', name=os.path.basename(filename), total=total,
        )
        try:
            with open(filename, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
        except Exception as e:
            if not quiet:
                console.print(f'[red] 写入失败: {e}[/red]')
            if os.path.exists(filename):
                os.remove(filename)
            return False

    size = os.path.getsize(filename)
    if not quiet:
        console.print(f'[green] 下载完成: {size / 1024 / 1024:.1f} MB[/green]')
    return True


def download_song(song: dict, subdir: str | None = None):
    """下载单曲到 {MUSIC_DIR}/[subdir]/"""
    console.clear()
    console.rule('[bold cyan]下载[/bold cyan]')
    console.print()

    sid = song['id']
    name = song['name']
    artists = song_artists(song)

    console.print(f'[bold]歌名:[/bold] {name}')
    console.print(f'[bold]歌手:[/bold] {artists}')
    console.print()

    # 检查本地曲库是否已存在
    local_file = _find_local_file(song)
    if local_file:
        console.print(f'[green] 本地已存在: {os.path.basename(local_file)}[/green]')
        if not Confirm.ask('仍要重新下载?'):
            return

    level, qdesc = choose_quality_for_download()

    with console.status(f'[yellow]获取音频URL ({qdesc})...'):
        try:
            r = apis.track.getTrackAudioV1([sid], level=level)
        except Exception as e:
            console.print(f'[red] 获取失败: {e}[/red]')
            return

    data = r.get('data', [])
    if not data:
        console.print('[red] 接口返回为空[/red]')
        return

    url = data[0].get('url', '')
    if not url:
        console.print(f'[yellow] 当前品质无可用URL[/yellow]')
        if level != 'standard':
            console.print('[yellow] 降级到 standard...[/yellow]')
            level, qdesc = QUALITY_MAP['1']
            with console.status(f'[yellow]重试 standard...'):
                try:
                    r = apis.track.getTrackAudioV1([sid], level='standard')
                except Exception as e:
                    console.print(f'[red] 获取失败: {e}[/red]')
                    return
            data2 = r.get('data', [])
            if not data2 or not data2[0].get('url'):
                console.print('[red] 无可用音频[/red]')
                return
            url = data2[0]['url']
        else:
            console.print('[red] 无可用音频[/red]')
            return

    ext = '.flac' if level in ('lossless', 'hires') else '.mp3'
    target = MUSIC_DIR if subdir is None else os.path.join(MUSIC_DIR, safe_name(subdir))
    os.makedirs(target, exist_ok=True)
    fname = os.path.join(target, f'{safe_name(artists)} - {safe_name(name)}{ext}')

    if os.path.exists(fname):
        console.print(f'[yellow] {os.path.basename(fname)} 已存在[/yellow]')
        if not Confirm.ask('覆盖?'):
            return

    console.print(f'[green] 开始下载: {fname}[/green]')
    download_with_progress(url, fname)


def download_all_songs(songs: list, subdir: str | None = None):
    """批量下载歌曲到 {MUSIC_DIR}/[subdir]/"""
    if not songs:
        console.print('[yellow] 无歌曲可下载[/yellow]')
        time.sleep(0.8)
        return

    import time

    level, qdesc = choose_quality_for_download()

    target = MUSIC_DIR if subdir is None else os.path.join(MUSIC_DIR, safe_name(subdir))
    os.makedirs(target, exist_ok=True)
    label = subdir or '曲库'
    console.print(f'\n[green]下载 {len(songs)} 首 → {target} ({qdesc})[/green]')

    ok = 0
    fail = 0
    for i, s in enumerate(songs, 1):
        sid = s['id']
        name = s['name']
        artists = song_artists(s)
        ext = '.flac' if level in ('lossless', 'hires') else '.mp3'
        fname = os.path.join(target, f'{safe_name(artists)} - {safe_name(name)}{ext}')

        # 检查本地曲库是否已存在（不限制当前目标目录，扫描整个 MUSIC_DIR）
        local_file = _find_local_file(s)
        if local_file:
            console.print(f'  [{i}/{len(songs)}] [green]本地已有: {name}[/green]')
            ok += 1
            continue

        console.print(f'  [{i}/{len(songs)}] [cyan]下载: {name}[/cyan]')
        try:
            r = apis.track.getTrackAudioV1([sid], level=level)
            data = r.get('data', [])
            if not data or not data[0].get('url'):
                if level != 'standard':
                    r2 = apis.track.getTrackAudioV1([sid], level='standard')
                    data2 = r2.get('data', [])
                    url = data2[0]['url'] if data2 and data2[0].get('url') else None
                else:
                    url = None
            else:
                url = data[0]['url']

            if not url:
                console.print(f'  [red]  无可用音频，跳过[/red]')
                fail += 1
                continue

            if download_with_progress(url, fname, quiet=True):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            console.print(f'  [red]  错误: {e}[/red]')
            fail += 1

    console.print(f'\n[green]批量下载完成: {ok} 成功, {fail} 失败[/green]')
    Prompt.ask('[dim]按回车返回[/dim]', default='')
