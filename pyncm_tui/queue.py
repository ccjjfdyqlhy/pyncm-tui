# queue — playback queue & modes
from __future__ import annotations


class PlaybackQueue:
    """播放队列：管理歌曲列表 + 播放模式"""

    MODES = ['sequential', 'list_loop', 'single_loop', 'shuffle']
    MODE_ICONS = {'sequential': '➡️', 'list_loop': '🔁', 'single_loop': '🔂', 'shuffle': '🔀'}

    def __init__(self):
        self.songs: list[dict] = []
        self._index: int = -1
        self.mode: str = 'list_loop'

    @property
    def current(self) -> dict | None:
        if 0 <= self._index < len(self.songs):
            return self.songs[self._index]
        return None

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def mode_icon(self) -> str:
        return self.MODE_ICONS.get(self.mode, '?')

    @property
    def mode_name_cn(self) -> str:
        names = {'sequential': '顺序播放', 'list_loop': '列表循环',
                 'single_loop': '单曲循环', 'shuffle': '随机播放'}
        return names.get(self.mode, self.mode)

    @property
    def position_str(self) -> str:
        if not self.songs:
            return '0/0'
        return f'{self._index + 1}/{len(self.songs)}'

    @property
    def has_next(self) -> bool:
        if not self.songs:
            return False
        if self.mode in ('list_loop', 'single_loop', 'shuffle'):
            return True
        return self._index < len(self.songs) - 1

    @property
    def is_last(self) -> bool:
        if self.mode == 'sequential':
            return self._index >= len(self.songs) - 1
        return False

    def add(self, song: dict) -> bool:
        self.songs.append(song)
        if len(self.songs) == 1:
            self._index = 0
            return True
        return False

    def play_now(self, song: dict):
        self.songs = [song]
        self._index = 0

    def set_current(self, idx: int):
        if 0 <= idx < len(self.songs):
            self._index = idx

    def next_song(self) -> dict | None:
        if not self.songs:
            return None
        n = len(self.songs)
        if self.mode == 'single_loop':
            return self.current
        elif self.mode in ('list_loop', 'shuffle'):
            self._index = (self._index + 1) % n
            return self.current
        else:  # sequential
            if self._index < n - 1:
                self._index += 1
                return self.current
            return None

    def prev_song(self) -> dict | None:
        if not self.songs:
            return None
        n = len(self.songs)
        if self.mode == 'single_loop':
            return self.current
        else:
            self._index = (self._index - 1) % n
            return self.current

    def toggle_mode(self):
        idx = self.MODES.index(self.mode)
        self.mode = self.MODES[(idx + 1) % len(self.MODES)]

    def remove(self, idx: int):
        if 0 <= idx < len(self.songs):
            self.songs.pop(idx)
            if idx < self._index:
                self._index -= 1
            elif idx == self._index:
                if self._index >= len(self.songs):
                    self._index = len(self.songs) - 1

    def clear(self):
        self.songs.clear()
        self._index = -1


queue = PlaybackQueue()
