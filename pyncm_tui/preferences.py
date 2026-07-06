# preferences — config file read/write
from __future__ import annotations

import json
import os

PREFERENCES_FILE = '.pyncm_prefs.json'

DEFAULTS = {
    'music_dir': '曲库',
    'default_quality': 'exhigh',
    'max_display': 50,
}

_prefs: dict | None = None


def _path() -> str:
    """偏好文件路径（在工作目录）"""
    return os.path.join(os.getcwd(), PREFERENCES_FILE)


def load() -> dict:
    global _prefs
    if _prefs is not None:
        return _prefs
    fpath = _path()
    if os.path.exists(fpath):
        try:
            with open(fpath, encoding='utf-8') as f:
                _prefs = {**DEFAULTS, **json.load(f)}
        except Exception:
            _prefs = dict(DEFAULTS)
    else:
        _prefs = dict(DEFAULTS)
    return _prefs


def save():
    if _prefs is None:
        return
    fpath = _path()
    try:
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(_prefs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get(key: str, default=None):
    return load().get(key, default)


def set(key: str, value):
    load()[key] = value
    save()
