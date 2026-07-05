# config — shared console & constants

import os

from pyncm import apis
from rich.console import Console

from .preferences import get as get_pref

console = Console()
SESSION_FILE = '.pyncm_session'
# 下载曲库目录，从偏好读取，可被环境变量覆盖
MUSIC_DIR = os.environ.get('NCM_MUSIC_DIR') or get_pref('music_dir', '曲库')

MAX_DISPLAY = 50  # 列表每页最大显示项数

QUALITY_MAP: dict[str, tuple[str, str]] = {
    '1': ('standard', '标准 128kbps'),
    '2': ('exhigh', '极高 320kbps'),
    '3': ('lossless', '无损 FLAC'),
    '4': ('hires', '高解析度 HIRES'),
}

# 默认品质 key（'1'~'4'），从偏好读取
_DEFAULT_QKEY = get_pref('default_quality', 'exhigh')
# 找到对应 key
DEFAULT_QUALITY_KEY = '2'
for k, (lv, _) in QUALITY_MAP.items():
    if lv == _DEFAULT_QKEY:
        DEFAULT_QUALITY_KEY = k
        break

SEARCH_TYPES: dict[str, tuple[int, str]] = {
    '1': (apis.cloudsearch.SONG, '歌曲'),
    '2': (apis.cloudsearch.ALBUM, '专辑'),
    '3': (apis.cloudsearch.ARTIST, '歌手'),
    '4': (apis.cloudsearch.PLAYLIST, '歌单'),
}
