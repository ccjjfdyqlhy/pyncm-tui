# pyncm TUI — 网易云音乐终端客户端

## 项目用途

基于 Rich + Pygame 的网易云音乐 TUI 客户端。功能：登录（Cookie）、搜索、歌单/专辑/歌手管理、在线播放、本地下载、歌词查看、每日推荐、签到。

## 架构

```
NCM/
├── pyncm/               # 网易云 API 库（第三方，不要动）
│   ├── apis/            #   各接口：login/album/artist/playlist/track/user...
│   └── utils/           #   工具：crypto/lrcparser/downloader...
│
├── pyncm_tui/           # 【当前入口】模块化 TUI（14 文件）
│   ├── __init__.py      #   main() 入口
│   ├── __main__.py      #   python -m pyncm_tui 支持
│   ├── config.py        #   全局常量：console/QUALITY_MAP/SEARCH_TYPES
│   ├── session.py       #   登录态管理
│   ├── menu.py          #   主菜单
│   ├── screens.py       #   所有列表/详情页（搜索/专辑/歌手/歌单/每日推荐）
│   ├── actions.py       #   歌曲操作菜单/队列管理/批量播放
│   ├── download.py      #   单曲/批量下载（注意：无 MUSIC_DIR 归类）
│   ├── engine.py        #   播放引擎（缓冲/切歌/音质切换/模式循环）
│   ├── player.py        #   Pygame 播放器单例
│   ├── queue.py         #   播放队列（顺序/循环/单曲/随机）
│   ├── key.py           #   非阻塞按键读取
│   ├── helpers.py       #   工具函数
│   └── lyrics.py        #   歌词展示
│
├── pyncm_tui.py         # ❌ 旧版单体文件（1938行，有MUSIC_DIR归类功能）
├── pyncm_tui.py.bak     # ❌ 更旧备份（1168行，已完全过时）
├── pyncm_downloader.py  # ❓ 独立CLI下载脚本（功能被pyncm_tui覆盖）
│
├── *.flac               # 已下载的音乐文件（用户数据，不要删）
└── .pyncm_session       # 登录态缓存文件（自动生成）
```

## 启动方式

```bash
# 推荐
cd /home/darkstar/NCM && python -m pyncm_tui

# 或直接运行
cd /home/darkstar/NCM/pyncm_tui && python __init__.py

# 依赖
pip install rich requests pygame
```

主入口：`pyncm_tui/__init__.py:main()` → login → `main_menu()` 循环。

## 功能矩阵

| 功能 | 说明 |
|------|------|
| 登录 | MUSIC_U Cookie 登录，自动缓存 |
| 搜索 | 歌曲/专辑/歌手/歌单，分页显示 |
| 歌单 | 查看/播放/下载我的全部歌单 |
| 专辑详情 | 查看歌曲列表、播放、下载 |
| 歌手 | 获取歌手热门 50 首 |
| 每日推荐 | 需登录 |
| 播放 | 队列式：顺序/列表循环/单曲循环/随机 |
| 音质切换 | 播放中按 `c` 实时切换 |
| 下载 | 品质选择：standard/exhigh/lossless/hires，自动降级 |
| 歌词 | 原文 + 翻译（前 30 行） |

## 可删除文件

| 文件 | 状态 | 原因 |
|------|------|------|
| **`pyncm_tui.py`** | ✅ 已删 | 旧版单体文件，功能已完全移植到模块化版本 |
| **`pyncm_tui.py.bak`** | ✅ 已删 | 更旧备份，无独立价值 |
| **`pyncm_downloader.py`** | ❓ 可选留 | 轻量 CLI 下载器，不依赖 Rich/pygame，纯命令行场景可能有用 |

### 删除前注意事项

1. **`pyncm_tui.py`** 上有最近添加的 `MUSIC_DIR` + `subdir` 归类下载功能（环境变量控制），而模块化版本 `pyncm_tui/download.py` 还没有此功能。**如果删掉 `pyncm_tui.py`，需先移植该功能到模块化版本**，否则下载会全部落 CWD。

2. **`.flac` 文件** — 用户下载的音乐数据，绝不能删。

3. **`.pyncm_session`** — 自动生成的登录缓存，删了下次需重新登录。

## 已实现功能 vs 旧版

`pyncm_tui.py` 中的 MUSIC_DIR 归类下载功能（`MUSIC_DIR` 环境变量 + 按专辑名/歌手名/歌单名/每日推荐自动子目录归类）已完全移植到 `pyncm_tui/` 模块化版本。两者功能一致。
