# engine — playback loop & per-song control

import os
import sys
import time
import tempfile

import requests
from rich.markup import escape
from rich.console import Group

from .config import console, QUALITY_MAP
from .key import get_key, _HAS_TERMIOS
from .helpers import fmt_dur, song_artists, song_album, song_dt, safe_name
from .helpers import lib_music_dir, lib_cover_dir, lib_meta_dir, lib_ensure_dirs, song_basename
from .player import player, get_audio_url
from .queue import queue


def _level_desc(level: str) -> str:
    """根据 level key 获取中文描述"""
    for _, (lv, desc) in QUALITY_MAP.items():
        if lv == level:
            return desc
    return level


def _find_local_file(song: dict) -> str | None:
    """在新曲库 music/ 子目录中查找已下载的本地文件。
    未找到则回退扫描旧版 MUSIC_DIR 根目录（兼容旧结构）。"""
    artists = song_artists(song)
    name = song['name']
    base = f'{safe_name(artists)} - {safe_name(name)}'

    # 1) 新结构：music/ 子目录（快速直接查找）
    music_dir = lib_music_dir()
    if os.path.isdir(music_dir):
        for f in os.listdir(music_dir):
            fname, ext = os.path.splitext(f)
            if fname == base and ext.lower() in ('.mp3', '.flac'):
                return os.path.join(music_dir, f)

    # 2) 回退：旧版 MUSIC_DIR 根目录递归扫描
    from .config import MUSIC_DIR
    if not os.path.isdir(MUSIC_DIR):
        return None
    for dirpath, _, filenames in os.walk(MUSIC_DIR):
        # 跳过新结构的子目录
        rel = os.path.relpath(dirpath, MUSIC_DIR)
        if rel in ('music', 'cover', 'lyric', 'metadata') or rel.startswith(('music/', 'cover/', 'lyric/', 'metadata/')):
            continue
        for f in filenames:
            fname, ext = os.path.splitext(f)
            if fname == base and ext.lower() in ('.mp3', '.flac'):
                return os.path.join(dirpath, f)
    return None


def _cover_url(song: dict) -> str:
    """从歌曲 dict 提取专辑封面 URL"""
    al = song.get('al', song.get('album', {}))
    return al.get('picUrl', '')


def _save_metadata(song: dict, playlists: list[str] | None = None):
    """保存歌曲元数据到 metadata/ 目录。
    若已有元数据，合并（保留已有歌单信息）。"""
    import json
    meta_dir = lib_meta_dir()
    os.makedirs(meta_dir, exist_ok=True)
    mpath = os.path.join(meta_dir, f'{song_basename(song)}.json')

    # 读取已有
    existing = {}
    if os.path.exists(mpath):
        try:
            with open(mpath, encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            pass

    artists = [a.get('name', '') for a in song.get('artists', song.get('ar', []))]
    al = song.get('al', song.get('album', {}))

    meta = {
        'id': song['id'],
        'name': song['name'],
        'artists': artists,
        'album': al.get('name', ''),
        'picUrl': _cover_url(song),
        'duration': song_dt(song),
    }

    # 合并已有歌单信息
    pl = dict(existing.get('playlists', {}))
    if playlists:
        for p in playlists:
            pl[p] = pl.get(p, 0) + 1
    if pl:
        meta['playlists'] = pl

    try:
        with open(mpath, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def download_cover(song: dict, save_dir: str | None = None) -> str | None:
    """下载专辑封面，保存为 PNG 格式（避免 JPEG 解码兼容性问题）。
    若 save_dir 为 None，保存到 cover/ 子目录。
    返回封面路径。失败返回 None。"""
    from PIL import Image as PILImage
    import io

    url = _cover_url(song)
    if not url:
        return None
    if save_dir is None:
        save_dir = lib_cover_dir()
    os.makedirs(save_dir, exist_ok=True)

    base = song_basename(song)
    png_path = os.path.join(save_dir, f'{base}.png')

    # 已有有效 PNG 缓存
    if os.path.exists(png_path):
        try:
            PILImage.open(png_path).load()
            return png_path
        except Exception:
            pass  # 损坏，重新下载

    # 删除旧 JPG 缓存（可能损坏或不完整）
    for ext in ('.jpg', '.jpeg'):
        old = os.path.join(save_dir, f'{base}{ext}')
        if os.path.exists(old):
            try:
                os.remove(old)
            except Exception:
                pass

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = PILImage.open(io.BytesIO(resp.content))
        img.load()                         # 验证图像可解码
        img.save(png_path, 'PNG')
        return png_path
    except Exception:
        # 清理可能留下的空文件
        if os.path.exists(png_path):
            try:
                os.remove(png_path)
            except Exception:
                pass
        return None


def _buffer_song(song: dict, level: str = 'standard') -> str | None:
    """下载歌曲到临时文件，返回路径。同时下载封面到同临时目录。
    失败返回 None。优先检查本地已有文件。"""
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
        # 下载封面到 cover/ 子目录（持久缓存）
        download_cover(song)
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
    使用 Rich Progress (BarColumn bright_cyan) 风格，参考 test_tui.py。
    返回: 'quit' | 'ended' | 'next' | 'prev'"""
    from rich.table import Table
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.live import Live
    from rich.console import Console
    from rich.text import Text as RText

    total_sec = song_dt(song) / 1000.0
    name = song["name"]
    artists = song_artists(song)
    album = song_album(song)

    # ── 封面：检查 cover/ 子目录，找不到则下载 ──
    cover_path = None
    base_name = song_basename(song)
    # 1) cover/ 子目录
    cover_dir = lib_cover_dir()
    if os.path.isdir(cover_dir):
        for f in os.listdir(cover_dir):
            fn, fext = os.path.splitext(f)
            if fn == base_name and fext.lower() in ('.jpg', '.jpeg', '.png'):
                cover_path = os.path.join(cover_dir, f)
                break
    # 2) 退回到音频同目录
    if not cover_path:
        audio_path = path_holder[0]
        adir = os.path.dirname(audio_path)
        if os.path.isdir(adir) and adir != cover_dir:
            for f in os.listdir(adir):
                fn, fext = os.path.splitext(f)
                if fn == base_name and fext.lower() in ('.jpg', '.jpeg', '.png'):
                    cover_path = os.path.join(adir, f)
                    break
    # 3) 验证找到的封面文件可读取；损坏则删除并重新下载
    if cover_path and os.path.exists(cover_path):
        try:
            from PIL import Image as PILImage
            PILImage.open(cover_path).load()
        except Exception:
            try:
                os.remove(cover_path)
            except Exception:
                pass
            cover_path = None
    # 4) 仍找不到或损坏 → 下载
    if not cover_path:
        cover_path = download_cover(song)
    has_cover = cover_path is not None and os.path.exists(cover_path)

    # ── 生成封面 ASCII 艺术（保留颜色）──
    cover_art_renderable = None
    if has_cover and cover_path:
        try:
            from ascii_magic import AsciiArt
            from ascii_magic.ascii_art import Modes
            art = AsciiArt.from_image(str(cover_path))
            ansi_str = art._img_to_art(columns=40, mode=Modes.TERMINAL, char='\u2588')
            cover_art_renderable = RText.from_ansi(ansi_str)
        except Exception:
            cover_art_renderable = None

    # ── 进度条 (Rich Progress, 风格参考 test_tui.py) ──
    progress = Progress(
        TextColumn("{task.fields[ct]}", style="yellow"),
        BarColumn(bar_width=40, complete_style="bright_cyan", finished_style="bright_cyan"),
        TextColumn("{task.fields[tt]}", style="yellow"),
    )
    play_task = progress.add_task(
        '',
        total=total_sec,
        ct=fmt_dur(0),
        tt=fmt_dur(song_dt(song)),
    )

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
    with Live(console=live_console, auto_refresh=False, refresh_per_second=4) as live:
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

            # ── 更新 last 值 ──
            last_pos = pos
            last_paused = paused
            last_vol = vol
            last_qpos = qpos
            last_mode = mode_cn
            last_src = src
            last_qlt = qlt

            # ── 更新进度条 ──
            progress.update(play_task, completed=pos, ct=fmt_dur(int(pos)), tt=fmt_dur(song_dt(song)))

            # ── 构建界面 (test_tui.py 风格) ──

            # Header: ✦ PLAYER ✦
            play_icon = "⏸" if paused else "▶"
            header_text = RText()
            header_text.append(f"✦ PLAYER ✦  {play_icon}", style="bold magenta")

            # Track info
            track_info = Table.grid(padding=(0, 2))
            track_info.add_column(style="dim", width=8)
            track_info.add_column()
            track_info.add_row("Track:", f"[bold cyan]{escape(name)}[/bold cyan]")
            track_info.add_row("Artist:", f"[green]{escape(artists)}[/green]")
            track_info.add_row("Album:", f"[dim]{escape(album)}[/dim]")

            # 右侧状态面板
            status = Table.grid(padding=(0, 2))
            status.add_column(width=2, style="dim")
            status.add_column(style="dim")
            status.add_row("📋", qpos)
            status.add_row(mode_icon, mode_cn)
            status.add_row("🔊", f"{int(vol * 100)}%")
            status.add_row(src_icon, f"{src} | {qlt}")
            if cover_art_renderable is not None:
                status.add_row("🎨", "[dim]ASCII 封面[/dim]")

            # 布局：左右分栏
            layout = Table.grid(padding=(0, 4))
            layout.add_column(ratio=3)
            layout.add_column(ratio=2, style="dim", justify="right")
            layout.add_row(track_info, status)

            # ── 操作栏（test_tui 风格: 简洁布局）──
            ctrl1 = RText()
            ctrl1.append("  ⏮ [b]    ⏸ [p]    ⏭ [n]   ", style="bold")
            ctrl2 = RText()
            ctrl2.append(f"  {mode_icon} {mode_cn} [m]  |  🎚️ {qlt} [c]  |  🔊 {int(vol*100)}% [+]/[-]", style="dim")
            ctrl3 = RText()
            ctrl3.append("  ⏪ [<]  ⏩ [>]  📋 [l]  ⏹ [s]  🚪 [q]", style="dim")

            # ── 组合 ──
            group_items = [
                "",
                header_text,
            ]
            if cover_art_renderable is not None:
                group_items.append("")
                group_items.append(cover_art_renderable)
            group_items.extend([
                "",
                layout,
                "",
                progress,
                "",
                ctrl1,
                ctrl2,
                ctrl3,
                "",
                "[dim]>[/dim]",
            ])
            inner = Group(*group_items)

            live.update(inner, refresh=True)


def _download_song_to_disk(song: dict, level: str, download_dir: str | None = None) -> str | None:
    """下载歌曲到本地 music/ 子目录，返回路径。已存在则跳过。
    同时保存封面到 cover/ 和元数据到 metadata/。"""
    lib_ensure_dirs()
    music_dir = lib_music_dir() if download_dir is None else download_dir
    os.makedirs(music_dir, exist_ok=True)

    ext = '.flac' if level in ('lossless', 'hires') else '.mp3'
    fname = f'{song_basename(song)}{ext}'
    fpath = os.path.join(music_dir, fname)

    if os.path.exists(fpath):
        return fpath  # 已存在，直接返回

    sid = song['id']
    url = get_audio_url(sid, level)
    if not url:
        return None

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(fpath, 'wb') as f:
            for chunk in resp.iter_content(32768):
                if chunk:
                    f.write(chunk)
        # 下载封面 + 写元数据
        download_cover(song)
        _save_metadata(song)
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
