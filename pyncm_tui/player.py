# player — pygame mixer singleton

import os
import subprocess
import tempfile

import pygame
from pyncm import apis


def _flac_to_wav(flac_path: str) -> str | None:
    """用 ffmpeg 将 FLAC 转码为临时 WAV，返回 WAV 路径。失败返回 None。"""
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-i', flac_path, '-acodec', 'pcm_s16le',
             '-ar', '44100', '-ac', '2', tmp_path],
            capture_output=True, check=True, timeout=60)
        return tmp_path
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None


class Player:
    """Singleton wrapper around pygame.mixer.music"""

    _instance: 'Player | None' = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        self.current_song: dict | None = None
        self.audio_file: str | None = None
        self.paused = False
        self.started_at = 0.0
        self._volume = 0.7
        self.current_level: str = 'standard'
        self.current_level_desc: str = '标准 128kbps'
        self._converted: str | None = None  # 转码产生的临时文件，stop 时清理
        self._original_audio: str | None = None  # 原始文件路径（转码前），用于 source_type 判断

    @property
    def playing(self) -> bool:
        return pygame.mixer.music.get_busy()

    @property
    def position(self) -> float:
        return pygame.mixer.music.get_pos() / 1000.0

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, v: float):
        self._volume = max(0.0, min(1.0, v))
        pygame.mixer.music.set_volume(self._volume)

    @property
    def source_type(self) -> str:
        """返回播放源: '本地' | '在线' | '未知'"""
        src = self._original_audio or self.audio_file
        if not src:
            return '未知'
        # tempfile 路径 → 在线流媒体；MUSIC_DIR路径 → 本地已下载
        if src.startswith(tempfile.gettempdir()):
            return '在线'
        return '本地'

    def play(self, audio_file: str, song: dict,
             level: str = 'standard', level_desc: str = '标准 128kbps'):
        self.stop()
        self.audio_file = audio_file
        self._original_audio = audio_file
        self.current_song = song
        self.current_level = level
        self.current_level_desc = level_desc
        self.paused = False

        # 某些 FLAC 文件 pygame 无法解码，自动转 WAV
        try:
            pygame.mixer.music.load(audio_file)
        except pygame.error as e:
            if audio_file.lower().endswith('.flac'):
                wav = _flac_to_wav(audio_file)
                if wav:
                    self._converted = wav
                    self.audio_file = wav
                    pygame.mixer.music.load(wav)
                else:
                    # 转码也失败，原样抛错
                    raise
            else:
                raise

        pygame.mixer.music.set_volume(self._volume)
        pygame.mixer.music.play()

    def stop(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.paused = False
        if self._converted:
            try:
                os.unlink(self._converted)
            except Exception:
                pass
            self._converted = None
        self._original_audio = None

    def toggle_pause(self):
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
        elif self.playing:
            pygame.mixer.music.pause()
            self.paused = True


player = Player()


def get_audio_url(sid: int, level: str = 'standard') -> str | None:
    """获取歌曲音频URL，失败自动降级"""
    for lv in [level, 'exhigh', 'standard']:
        try:
            r = apis.track.getTrackAudioV1([sid], level=lv)
            data = r.get('data', [])
            if data and data[0].get('url'):
                return data[0]['url']
        except Exception:
            pass
    return None
