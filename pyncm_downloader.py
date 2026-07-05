#!/usr/bin/env python3
import os
import re
import sys

from pyncm import apis, dumpSessionAsString, getCurrentSession, loadSessionFromString, setCurrentSession, writeLoginInfo
from pyncm.utils.downloader import Downloader

SESSION_FILE = '.pyncm_session'
QUALITY_MAP = {
    '1': ('standard', '标准 128kbps'),
    '2': ('exhigh', '极高 320kbps'),
    '3': ('lossless', '无损 FLAC'),
    '4': ('hires', '高解析度 HIRES'),
}


def save_session():
    with open(SESSION_FILE, 'w') as f:
        f.write(dumpSessionAsString(getCurrentSession()))
    print(f'[+] 登录态已保存到 {SESSION_FILE}')


def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE) as f:
            setCurrentSession(loadSessionFromString(f.read().strip()))
        return True
    return False


def login():
    if load_session():
        try:
            r = apis.login.getCurrentLoginStatus()
            if r.get('code') == 200 and r.get('account'):
                print(f'[+] 已恢复登录态')
                return
        except Exception:
            pass
        print('[-] 登录态已过期，请重新登录')

    print('''
[!] 二维码登录 API 不可用，请使用 Cookie 登录:
  1. 用浏览器打开 https://music.163.com 并登录
  2. 按 F12 打开开发者工具
  3. 转到 Application / 存储 -> Cookies -> music.163.com
  4. 找到 MUSIC_U 并复制其值
''')
    music_u = input('MUSIC_U: ').strip()
    if not music_u:
        print('[-] 已取消')
        sys.exit(1)

    try:
        r = apis.login.loginViaCookie(MUSIC_U=music_u)
        if r.get('code') == 200:
            print(f'[+] 登录成功！')
            save_session()
        else:
            print(f'[-] 登录失败: {r}')
            sys.exit(1)
    except Exception as e:
        print(f'[-] 登录异常: {e}')
        sys.exit(1)


def choose_quality():
    print('\n--- 选择品质 ---')
    for k, (_, desc) in QUALITY_MAP.items():
        print(f'  [{k}] {desc}')
    while True:
        c = input('请选择 (默认2): ').strip() or '2'
        if c in QUALITY_MAP:
            return QUALITY_MAP[c]
        print('无效选择，请重试')


def search_and_select():
    keyword = input('\n搜索关键词: ').strip()
    if not keyword:
        return None

    print(f'[+] 搜索 "{keyword}" ...')
    try:
        r = apis.cloudsearch.getSearchResult(keyword, stype=apis.cloudsearch.SONG, limit=20)
    except Exception as e:
        print(f'[-] 搜索失败: {e}')
        return None

    songs = r.get('result', {}).get('songs', [])
    if not songs:
        print('[-] 未找到结果')
        return None

    print(f'\n--- 搜索结果 ({len(songs)} 条) ---')
    for i, s in enumerate(songs, 1):
        artists = ', '.join(a['name'] for a in s.get('artists', s.get('ar', [])))
        album = s.get('album', s.get('al', {})).get('name', '?')
        dur = s.get('duration', s.get('dt', 0)) // 1000
        mm, ss = divmod(dur, 60)
        print(f'  [{i:2d}] {s["name"]}  |  {artists}  |  {album}  |  {mm:02d}:{ss:02d}')

    while True:
        try:
            c = input(f'\n请选择歌曲序号 (1-{len(songs)}, 回车取消): ').strip()
            if not c:
                return None
            idx = int(c) - 1
            if 0 <= idx < len(songs):
                return songs[idx]
            print(f'请输入 1-{len(songs)}')
        except ValueError:
            print('请输入数字')


def download_song(song, quality_level, quality_name):
    song_id = song['id']
    name = song['name']
    artists = ', '.join(a['name'] for a in song.get('artists', song.get('ar', [])))
    safe_name = re.sub(r'[<>:"/\\|?*]', '', f'{artists} - {name}')
    filename = f'{safe_name}.mp3'
    if quality_level in ('lossless', 'hires'):
        filename = f'{safe_name}.flac'

    if os.path.exists(filename):
        print(f'[!] {filename} 已存在，跳过')
        return

    print(f'[+] 获取音频URL (品质: {quality_name}) ...')
    try:
        r = apis.track.getTrackAudioV1([song_id], level=quality_level)
    except Exception as e:
        print(f'[-] 获取失败: {e}')
        return

    data = r.get('data', [])
    if not data:
        print('[-] 接口返回为空')
        return

    url = data[0].get('url', '')
    if not url:
        print(f'[-] 无可用URL (可能需要 {quality_name} VIP 权限)')
        if quality_level != 'standard':
            print('[!] 尝试降级到 standard ...')
            return download_song(song, 'standard', '标准 128kbps')
        return

    print(f'[+] 开始下载: {filename}')
    dl = Downloader(pool_size=4, timeout=15)
    dl.append(url, filename)
    dl.wait()
    if os.path.exists(filename):
        size = os.path.getsize(filename)
        print(f'[+] 下载完成: {filename} ({size / 1024 / 1024:.1f} MB)')
    else:
        print('[-] 下载似乎未完成')


def main():
    login()
    while True:
        song = search_and_select()
        if song is None:
            break
        quality_level, quality_name = choose_quality()
        download_song(song, quality_level, quality_name)
        again = input('\n继续下载? (y/n, 默认y): ').strip().lower()
        if again == 'n':
            break
    print('再见~')


if __name__ == '__main__':
    main()
