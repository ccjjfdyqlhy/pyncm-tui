# helpers — utility functions

import os
import re

from .config import MAX_DISPLAY
from .preferences import get as get_pref


def clear_screen():
    """清空终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')


# ── 曲库路径函数 ────────────────────────────────────────────────────────

def lib_root() -> str:
    return get_pref('music_dir', '曲库')


def lib_music_dir() -> str:
    return os.path.join(lib_root(), 'music')


def lib_cover_dir() -> str:
    return os.path.join(lib_root(), 'cover')


def lib_lyric_dir() -> str:
    return os.path.join(lib_root(), 'lyric')


def lib_meta_dir() -> str:
    return os.path.join(lib_root(), 'metadata')


def lib_ensure_dirs():
    """确保曲库子目录存在"""
    for d in (lib_music_dir(), lib_cover_dir(), lib_lyric_dir(), lib_meta_dir()):
        os.makedirs(d, exist_ok=True)


def song_basename(song: dict) -> str:
    """返回歌曲的基础文件名（不含扩展名）：{Artist} - {Name}"""
    return f'{safe_name(song_artists(song))} - {safe_name(song["name"])}'


def fmt_dur(ms: int) -> str:
    s = ms // 1000
    m, sec = divmod(s, 60)
    return f'{m:02d}:{sec:02d}'


def safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', name)


def song_artists(s: dict) -> str:
    return ', '.join((a.get('name', '') or '') for a in s.get('artists', s.get('ar', [])))


def song_album(s: dict) -> str:
    return s.get('album', s.get('al', {})).get('name', '?')


def song_dt(s: dict) -> int:
    return s.get('duration', s.get('dt', 0))


def paged_slice(total: int, page: int, page_size: int = MAX_DISPLAY) -> tuple[int, int, int]:
    """(start, end, pages) for pagination"""
    pages = (total + page_size - 1) // page_size
    start = page * page_size
    end = min(start + page_size, total)
    return start, end, pages
