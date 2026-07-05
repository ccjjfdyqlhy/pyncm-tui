# PyNCM - Netease Cloud Music Python API & Tools

[![Version](https://img.shields.io/badge/version-1.8.1-blue.svg)](https://github.com/mos9527/pyncm)
[![Python](https://img.shields.io/badge/python-3.6+-green.svg)](https://www.python.org/downloads/)

Unofficial Python API for Netease Cloud Music (网易云音乐), featuring full API coverage, authentication management, and download utilities.

## Features

- **Complete API Coverage** - Search, tracks, albums, artists, playlists, users, cloud storage, videos, and more
- **Session Management** - Persistent login state with serialization support
- **Authentication** - Cellphone, email, and cookie-based login methods
- **Download Utility** - Multi-quality audio download (128kbps to Hi-Res)
- **TUI Interface** - Terminal-based music player and downloader
- **Encryption Support** - AES/EAPI encryption for all API requests

## Installation

```bash
# Clone the repository
git clone https://github.com/mos9527/pyncm.git
cd pyncm

# Install dependencies (pip will be configured in future releases)
pip install requests
```

## Quick Start

### Basic API Usage

```python
from pyncm import apis

# Login via phone
apis.loginViaCellphone(phone='13800138000', password='your_password', ctcode=86)

# Get track details
track = apis.track.getTrackDetail(29732235)
print(f"Song: {track['songs'][0]['name']}")

# Search songs
results = apis.cloudsearch.getSearchResult("周杰伦", stype=apis.cloudsearch.SONG)
for song in results['result']['songs'][:5]:
    print(f"{song['name']} - {song['ar'][0]['name']}")
```

### Session Management

```python
import pyncm

# Get current session
session = pyncm.getCurrentSession()
print(f"User: {session.nickname}")
print(f"VIP: {session.vipType}")

# Save session to string
session_dump = pyncm.dumpSessionAsString(session)

# Restore session later
pyncm.setCurrentSession(pyncm.loadSessionFromString(session_dump))
```

### Download Music

```bash
# Interactive downloader script
python pyncm_downloader.py
```

The downloader supports:
- Cookie-based login (recommended)
- Multiple quality levels: Standard, High, Lossless, Hi-Res
- Automatic format selection (MP3/FLAC)
- Resume from saved sessions

### TUI Interface

```bash
# Launch terminal UI
python -m pyncm_tui
```

Features:
- Interactive menu navigation
- Playlist browsing
- Built-in audio player
- Batch download
- Lyrics display

## API Modules

| Module | Description |
|--------|-------------|
| `pyncm.apis.login` | Authentication & user session |
| `pyncm.apis.track` | Track details, audio, comments |
| `pyncm.apis.album` | Album information & tracks |
| `pyncm.apis.artist` | Artist details, albums, songs |
| `pyncm.apis.playlist` | Playlist operations |
| `pyncm.apis.cloudsearch` | Search functionality |
| `pyncm.apis.user` | User profile & playlists |
| `pyncm.apis.cloud` | Cloud storage management |
| `pyncm.apis.video` | Video content |
| `pyncm.utils.downloader` | Download utilities |

## Authentication Methods

### Cookie Login (Recommended)

```python
# Get MUSIC_U from browser cookies after logging in to music.163.com
apis.login.loginViaCookie(MUSIC_U='your_cookie_value')
```

### Cellphone Login

```python
apis.loginViaCellphone(
    phone='13800138000',
    password='password',
    ctcode=86  # Country code
)
```

### Email Login

```python
apis.loginViaEmail(email='user@example.com', password='password')
```

## Audio Quality Levels

| Level | Name | Extension | VIP Required |
|-------|------|-----------|--------------|
| `standard` | Standard 128kbps | .mp3 | No |
| `exhigh` | Higher 320kbps | .mp3 | No |
| `lossless` | Lossless FLAC | .flac | Yes |
| `hires` | Hi-Res | .flac | Yes |

## Project Structure

```
NCM/
├── pyncm/                    # Core API library
│   ├── apis/                 # API modules
│   │   ├── login.py
│   │   ├── track.py
│   │   ├── album.py
│   │   ├── playlist.py
│   │   ├── artist.py
│   │   ├── cloudsearch.py
│   │   ├── user.py
│   │   ├── cloud.py
│   │   ├── video.py
│   │   └── miniprograms/     # Mini-program APIs
│   └── utils/                # Utilities
│       ├── crypto.py         # Encryption (AES/EAPI)
│       ├── downloader.py     # Download engine
│       ├── lrcparser.py      # Lyrics parser
│       └── ...
├── pyncm_tui/                # Terminal UI
│   ├── screens.py
│   ├── player.py
│   ├── download.py
│   └── ...
├── pyncm_downloader.py       # CLI downloader
└── README.md
```

## Notes

- **Overseas Users**: May encounter 460 'cheating' errors. Add header:
  ```python
  pyncm.getCurrentSession().headers['X-Real-IP'] = '118.88.88.88'
  ```
- **Rate Limiting**: Implement delays between requests to avoid IP blocking
- **VIP Content**: Some tracks require VIP membership for higher quality
- **QR Code Login**: Currently unavailable, use cookie or phone/email login

## Requirements

- Python 3.6+
- requests
- Optional: urwid (for TUI interface)

## License

This project is for educational purposes only. Please respect Netease Cloud Music's terms of service and copyright laws.

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## Disclaimer

This is an unofficial, third-party tool not affiliated with Netease, Inc. Use at your own risk.