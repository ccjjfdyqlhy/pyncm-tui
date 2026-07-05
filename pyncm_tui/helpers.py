# helpers — utility functions

import re

from .config import MAX_DISPLAY


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
