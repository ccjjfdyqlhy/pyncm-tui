# config — shared console & constants

import os

from pyncm import apis

from rich.console import Console

console = Console()
SESSION_FILE = '.pyncm_session'
# 下载曲库目录。所有歌曲按来源自动归类到子文件夹。
# 可通过环境变量 NCM_MUSIC_DIR 覆盖
MUSIC_DIR = os.environ.get('NCM_MUSIC_DIR', '曲库')

MAX_DISPLAY = 50  # 列表每页最大显示项数

QUALITY_MAP: dict[str, tuple[str, str]] = {
    '1': ('standard', '标准 128kbps'),
    '2': ('exhigh', '极高 320kbps'),
    '3': ('lossless', '无损 FLAC'),
    '4': ('hires', '高解析度 HIRES'),
}

SEARCH_TYPES: dict[str, tuple[int, str]] = {
    '1': (apis.cloudsearch.SONG, '歌曲'),
    '2': (apis.cloudsearch.ALBUM, '专辑'),
    '3': (apis.cloudsearch.ARTIST, '歌手'),
    '4': (apis.cloudsearch.PLAYLIST, '歌单'),
}
