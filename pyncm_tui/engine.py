# engine — playback loop & per-song control

import os
import sys
import time
import tempfile

import requests
from rich.text import Text
from rich.markup import escape
from rich.panel import Panel
from rich.console import Group
from rich.progress import Progress, BarColumn, TextColumn

from .config import console, QUALITY_MAP, MUSIC_DIR
from .key import get_key, _HAS_TERMIOS
from .helpers import fmt_dur, song_artists, song_album, song_dt, safe_name
from .player import player, get_audio_url
from .queue import queue


def _level_desc(level: str) -> str:
    """根据 level key 获取中文描述"""
    for _, (lv, desc) in QUALITY_MAP.items():
        if lv == level:
            return desc
    return level


def _find_local_file(song: dict) -> str | None:
    """递归搜索 MUSIC_DIR，找已下载的本地文件"""
    artists = song_artists(song)
    name = song['name']
    base = f'{safe_name(artists)} - {safe_name(name)}'

    if not os.path.isdir(MUSIC_DIR):
        return None

    for dirpath, _, filenames in os.walk(MUSIC_DIR):
        for f in filenames:
            fname, ext = os.path.splitext(f)
            if fname == base and ext.lower() in ('.mp3', '.flac'):
                return os.path.join(dirpath, f)
    return None


def _buffer_song(song: dict, level: str = 'standard') -> str | None:
    """下载歌曲到临时文件，返回路径。失败返回 None。优先检查本地已有文件。"""
    # 优先使用本地文件
    local = _find_local_file(song)
    if local:
        console.print(f'[green] 本地文件: {os.path.basename(local)}[/green]')
        return local

    sid = song['id']
    url = get_audio_url(sid, level)
    if not url:
        return None

    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(tmp_path, 'wb') as f:
            for chunk in resp.iter_content(32768):
                if chunk:
                    f.write(chunk)
        return tmp_path
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None


def _switch_quality(path_holder: list, song: dict):
    """切换当前歌曲音质：重新缓冲并续播"""
    pos = player.position
    console.print('\n[bold]选择音质:[/bold]')
    for k, (_, desc) in QUALITY_MAP.items():
        console.print(f'  [{k}] {desc}')
    console.print('  [回车] 取消')
    q = get_key(timeout=5.0)
    if q is None or q not in QUALITY_MAP:
        return
    level, qdesc = QUALITY_MAP[q]
    console.print(f'[yellow] 切换至 {qdesc}...[/yellow]')
    new_path = _buffer_song(song, level)
    if new_path is None:
        console.print('[red] 该音质无可用音频[/red]')
        time.sleep(0.8)
        return
    # 清理旧临时文件
    old_path = path_holder[0]
    try:
        os.unlink(old_path)
    except Exception:
        pass
    path_holder[0] = new_path
    player.play(new_path, song, level=level, level_desc=qdesc)
    # 尝试续播到之前位置
    import pygame
    if pos > 0 and pos < song_dt(song) / 1000.0:
        pygame.mixer.music.play(start=pos)
    console.print(f'[green] 已切换至 {qdesc}[/green]')
    time.sleep(0.5)


def _seek_pygame(audio_file: str, song: dict, pos_sec: float):
    """Seek by reloading audio at approximate position"""
    import pygame
    pygame.mixer.music.stop()
    pygame.mixer.music.unload()
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.set_volume(player.volume)
    pygame.mixer.music.play(start=pos_sec)


def _local_quality_desc(path: str) -> str:
    """根据本地文件扩展名返回质量描述"""
    if path.lower().endswith('.flac'):
        return '无损 FLAC'
    elif path.lower().endswith('.mp3'):
        return '本地 MP3'
    return '本地文件'


def playback_loop():
    """队列播放主循环。自动处理切歌、自动下一首、模式切换。"""
    while queue.current is not None:
        song = queue.current

        level = player.current_level
        level_desc = player.current_level_desc
        tmp_path = _buffer_song(song, level=level)
        # 本地文件 → 用实际扩展名显示质量
        if tmp_path and not tmp_path.startswith(tempfile.gettempdir()):
            level_desc = _local_quality_desc(tmp_path)
        if tmp_path is None:
            # 当前音质无可用音频，降级
            level = 'standard'
            level_desc = '标准 128kbps'
            tmp_path = _buffer_song(song, level=level)
        if tmp_path is None:
            console.print(f'[red] 跳过: {song["name"]} 无可用音频[/red]')
            time.sleep(0.8)
            queue.next_song()
            continue

        player.play(tmp_path, song, level=level, level_desc=level_desc)

        # 使用可变容器，允许音质切换更新路径
        path_holder = [tmp_path]
        result = _playback_control(path_holder, song)
        tmp_path = path_holder[0]

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        if result == 'quit':
            break
        elif result == 'ended':
            if queue.mode == 'single_loop':
                continue
            elif queue.is_last:
                break
            else:
                queue.next_song()
        elif result == 'next':
            queue.next_song()
        elif result == 'prev':
            queue.prev_song()

    player.stop()



def _playback_control(path_holder: list, song: dict) -> str:
    """单曲控制循环。path_holder[0] 为当前临时文件路径，音质切换时会更新。
    返回: 'quit' | 'ended' | 'next' | 'prev'"""
    from rich.table import Table

    total_sec = song_dt(song) / 1000.0
    name = song["name"]
    artists = song_artists(song)
    album = song_album(song)

    while True:
        if not player.playing and not player.paused:
            return "ended"

        pos = player.position
        pct = min(pos / total_sec * 100, 100) if total_sec > 0 else 0

        if _HAS_TERMIOS or sys.platform == "win32":
            console.clear()

        # ── 左侧：歌曲信息 ──
        info = Table.grid(padding=(0, 2))
        info.add_column(width=2)  # emoji
        info.add_column()         # text
        info.add_row("💿", f"[bold cyan]{name}[/bold cyan]")
        info.add_row("🎤", f"[green]{artists}[/green]")
        info.add_row("💽", f"[dim]{album}[/dim]")

        # ── 右侧：播放状态 ──
        qpos = queue.position_str
        mode_cn = queue.mode_name_cn
        mode_icon = queue.mode_icon
        vol = f"{int(player.volume * 100)}%"
        src = player.source_type
        src_icon = "💾" if src == "本地" else "🌐"
        qlt = player.current_level_desc

        status = Table.grid(padding=(0, 2))
        status.add_column(width=2, style="dim")
        status.add_column(style="dim")
        status.add_row("📋", qpos)
        status.add_row(mode_icon, mode_cn)
        status.add_row("🔊", vol)
        status.add_row(src_icon, src)
        status.add_row("🎚️", qlt)

        # ── 进度条 (Rich) ──
        time_str = f"{fmt_dur(int(pos * 1000))} / {fmt_dur(song_dt(song))}"
        play_icon = "⏸️" if player.paused else "▶️"
        play_style = "bold yellow" if player.paused else "yellow"

        pbar = Progress(
            TextColumn("  "),
            BarColumn(bar_width=None, style="cyan", complete_style="cyan"),
            TextColumn(f"  {time_str}  "),
            TextColumn(play_icon, style=play_style),
            expand=True,
        )
        pbar.add_task("", total=max(total_sec, 1), completed=pos)

        # ── 操作栏 第一行：媒体控制 ──
        c1 = Text()
        c1.append("  ")
        c1.append("⏹ ", style="bold red")
        c1.append("[s] ", style="red dim")
        c1.append("⏮ ", style="bold")
        c1.append("[b] ", style="dim")
        if player.paused:
            c1.append("▶️ ", style="bold green")
        else:
            c1.append("⏸️ ", style="bold yellow")
        c1.append("[p] ", style="dim")
        c1.append("⏭ ", style="bold")
        c1.append("[n] ", style="dim")
        c1.append("🔀 ", style="bold")
        c1.append("[m] ", style="dim")

        # ── 操作栏 第二行：辅助控制 ──
        c2 = Text()
        c2.append("  ")
        c2.append("⏪ ", style="dim")
        c2.append("[<] ", style="dim")
        c2.append("⏩ ", style="dim")
        c2.append("[>] ", style="dim")
        c2.append("🎚️ ", style="bold")
        c2.append("[c] ", style="dim")
        c2.append("➕ ", style="bold")
        c2.append("[+] ", style="dim")
        c2.append("➖ ", style="bold")
        c2.append("[-] ", style="dim")
        c2.append("📋 ", style="bold")
        c2.append("[l] ", style="dim")
        c2.append("🚪 ", style="bold red")
        c2.append("[q] ", style="red dim")

        # ── 布局：左右分栏 ──
        layout = Table.grid(padding=(0, 4))
        layout.add_column(ratio=3)
        layout.add_column(ratio=2, style="dim", justify="right")
        layout.add_row(info, status)

        # ── 用 Panel 包裹 ──
        inner = Group(
            "",
            layout,
            "",
            "",
            pbar,
            "",
            "",
            c1,
            "",
            c2,
            "",
        )

        console.print(Panel(inner, title="\U0001f3b5 \u64ad\u653e\u4e2d", border_style="cyan"))

        key = get_key(timeout=0.5)
        if key is None:
            continue

        if key == "q":
            player.stop()
            return "quit"
        elif key == "p":
            player.toggle_pause()
        elif key == "s":
            player.stop()
            return "quit"
        elif key == "n":
            if queue.has_next:
                player.stop()
                return "next"
            else:
                console.print("\n[yellow] \u961f\u5217\u5df2\u5230\u5e95[/yellow]")
                time.sleep(0.6)
        elif key == "b":
            player.stop()
            return "prev"
        elif key == "m":
            queue.toggle_mode()
        elif key == "l":
            from .actions import queue_screen
            queue_screen()
        elif key == "+":
            player.volume = min(1.0, player.volume + 0.1)
        elif key == "-":
            player.volume = max(0.0, player.volume - 0.1)
        elif key == "c":
            _switch_quality(path_holder, song)
        elif key == ">":
            new_pos = min(pos + 5, total_sec)
            _seek_pygame(path_holder[0], song, new_pos)
        elif key == "<":
            new_pos = max(pos - 5, 0)
            _seek_pygame(path_holder[0], song, new_pos)


def _download_song_to_disk(song: dict, level: str, download_dir: str | None = None) -> str | None:
    """下载歌曲到本地磁盘（非临时文件），返回路径。已存在则跳过下载。
    默认保存到 MUSIC_DIR。"""
    if download_dir is None:
        download_dir = MUSIC_DIR
    os.makedirs(download_dir, exist_ok=True)

    ext = '.flac' if level in ('lossless', 'hires') else '.mp3'
    fname = f'{safe_name(song_artists(song))} - {safe_name(song["name"])}{ext}'
    fpath = os.path.join(download_dir, fname)

    if os.path.exists(fpath):
        return fpath  # 已存在，直接返回

    sid = song['id']
    url = get_audio_url(sid, level)
    if not url:
        return None

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        total = int(resp.headers.get('content-length', 0))
        with open(fpath, 'wb') as f:
            for chunk in resp.iter_content(32768):
                if chunk:
                    f.write(chunk)
        return fpath
    except Exception:
        try:
            os.unlink(fpath)
        except Exception:
            pass
        return None


def playback_loop_with_download(level: str = 'standard'):
    """边下载边顺序播放。每首歌先下载到本地磁盘，再从本地文件播放。"""
    while queue.current is not None:
        song = queue.current
        name = song['name']
        artists = song_artists(song)

        # 先检查本地
        local = _find_local_file(song)
        if local:
            fpath = local
            console.print(f'[green] 本地: {name} — {artists}[/green]')
        else:
            console.print(f'[cyan] 下载: {name} — {artists}[/cyan]')
            fpath = _download_song_to_disk(song, level)

        if fpath is None:
            console.print(f'[red] 跳过: {name} 无可用音频[/red]')
            time.sleep(0.8)
            queue.next_song()
            continue

        # 本地文件 → 用实际扩展名显示质量
        if local:
            level_desc = _local_quality_desc(fpath)
        else:
            level_desc = _level_desc(level)
        player.play(fpath, song, level=level, level_desc=level_desc)
        console.print(f'[green] 播放: {name}[/green]')

        # 使用可变容器（虽然本地文件不会被删除，但保持接口一致）
        path_holder = [fpath]
        result = _playback_control(path_holder, song)

        if result == 'quit':
            break
        elif result == 'ended':
            if queue.mode == 'single_loop':
                continue
            elif queue.is_last:
                break
            else:
                queue.next_song()
        elif result == 'next':
            queue.next_song()
        elif result == 'prev':
            queue.prev_song()

    player.stop()
