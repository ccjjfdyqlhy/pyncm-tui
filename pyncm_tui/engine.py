# engine — playback loop & per-song control

import os
import sys
import time
import tempfile

import requests
from rich.text import Text
from rich.markup import escape
from rich.console import Group

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

        # 播放控制循环（可能需要重启多次）
        while True:
            result = _playback_control(path_holder, song)
            if result != "restart":
                break

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
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.live import Live
    from rich.console import Console

    total_sec = song_dt(song) / 1000.0
    name = song["name"]
    artists = song_artists(song)
    album = song_album(song)

    # 操作栏（静态）
    c1 = Text()
    c1.append("  ⏹ [s]  ⏮ [b]  ⏸ [p]  ⏭ [n]  🔀 [m]")
    c2 = Text()
    c2.append("  ⏪ [<]  ⏩ [>]  🎚️ [c]  ➕ [+]  ➖ [-]  📋 [l]  🚪 [q]")

    last_pos = -1.0
    last_paused = None
    last_vol = -1.0
    last_qpos = None
    last_mode = None
    last_src = None
    last_qlt = None

    # 创建一个用于 Live 的 Console（不限制宽度）
    live_console = Console(force_terminal=True)

    # 使用 auto_refresh=False，手动控制刷新
    with Live(console=live_console, auto_refresh=False, refresh_per_second=2) as live:
        while True:
            if not player.playing and not player.paused:
                return "ended"

            pos = player.position
            paused = player.paused
            vol = player.volume
            qpos = queue.position_str
            mode_cn = queue.mode_name_cn
            mode_icon = queue.mode_icon
            src = player.source_type
            src_icon = "💾" if src == "本地" else "🌐"
            qlt = player.current_level_desc

            # 检查是否有状态变化
            pos_changed = abs(pos - last_pos) >= 0.5
            paused_changed = paused != last_paused
            vol_changed = abs(vol - last_vol) > 0.01
            qpos_changed = qpos != last_qpos
            mode_changed = mode_cn != last_mode
            src_changed = src != last_src
            qlt_changed = qlt != last_qlt

            need_update = pos_changed or paused_changed or vol_changed or qpos_changed or mode_changed or src_changed or qlt_changed

            key = get_key(timeout=0.5)
            if key is not None:
                need_update = True

                if key == "q":
                    live.stop()
                    player.stop()
                    return "quit"
                elif key == "p":
                    player.toggle_pause()
                    paused = player.paused
                    paused_changed = True
                elif key == "s":
                    live.stop()
                    player.stop()
                    return "quit"
                elif key == "n":
                    if queue.has_next:
                        live.stop()
                        player.stop()
                        return "next"
                elif key == "b":
                    live.stop()
                    player.stop()
                    return "prev"
                elif key == "m":
                    queue.toggle_mode()
                elif key == "l":
                    from .actions import queue_screen
                    live.stop()
                    queue_screen()
                    last_pos = -1
                    # 返回后重新启动 Live
                    continue
                elif key == "+":
                    player.volume = min(1.0, player.volume + 0.1)
                    vol = player.volume
                    vol_changed = True
                elif key == "-":
                    player.volume = max(0.0, player.volume - 0.1)
                    vol = player.volume
                    vol_changed = True
                elif key == "c":
                    _switch_quality(path_holder, song)
                    qlt = player.current_level_desc
                    qlt_changed = True
                elif key == ">":
                    new_pos = min(pos + 5, total_sec)
                    _seek_pygame(path_holder[0], song, new_pos)
                    pos = new_pos
                    pos_changed = True
                elif key == "<":
                    new_pos = max(pos - 5, 0)
                    _seek_pygame(path_holder[0], song, new_pos)
                    pos = new_pos
                    pos_changed = True

            if not need_update:
                continue

            # 更新 last 值
            last_pos = pos
            last_paused = paused
            last_vol = vol
            last_qpos = qpos
            last_mode = mode_cn
            last_src = src
            last_qlt = qlt

            # ── 构建界面 ──

            # 左侧：歌曲信息
            info = Table.grid(padding=(0, 2))
            info.add_column(width=2)
            info.add_column()
            info.add_row("💿", f"[bold cyan]{name}[/bold cyan]")
            info.add_row("🎤", f"[green]{artists}[/green]")
            info.add_row("💽", f"[dim]{album}[/dim]")

            # 右侧：播放状态
            status = Table.grid(padding=(0, 2))
            status.add_column(width=2, style="dim")
            status.add_column(style="dim")
            status.add_row("📋", qpos)
            status.add_row(mode_icon, mode_cn)
            status.add_row("🔊", f"{int(vol * 100)}%")
            status.add_row(src_icon, src)
            status.add_row("🎚️", qlt)

            # 布局：左右分栏
            layout = Table.grid(padding=(0, 4))
            layout.add_column(ratio=3)
            layout.add_column(ratio=2, style="dim", justify="right")
            layout.add_row(info, status)

            # ── 进度条（手动渲染，总宽度 64）──
            # 格式：[进度条]  时间   图标
            time_str = f"{fmt_dur(int(pos * 1000))} / {fmt_dur(song_dt(song))}"
            play_icon = "⏸️" if paused else "▶️"

            # 计算进度条宽度：64 - 时间长度(13) - 3空格 - emoji(2列) = 46
            bar_width = 46
            filled = int((pos / total_sec) * bar_width) if total_sec > 0 else 0
            filled = max(0, min(filled, bar_width))
            bar_visual = "█" * filled + "░" * (bar_width - filled)
            pbar_text = Text()
            pbar_text.append(bar_visual, style="cyan")
            pbar_text.append(f"  {time_str}   {play_icon}")

            # ── 组合所有内容 ──
            inner = Group(
                "",
                layout,
                "",
                "",
                pbar_text,
                "",
                "",
                c1,
                "",
                c2,
                "",
                "",
                "[dim]>[/dim]",  # 输入提示符
            )

            live.update(inner, refresh=True)


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

        # 播放控制循环（可能需要重启多次）
        while True:
            result = _playback_control(path_holder, song)
            if result != "restart":
                break

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
