# screens — all list/detail pages

from pyncm import apis, getCurrentSession
from rich.table import Table
from rich.prompt import Prompt

from rich.markup import escape
from .config import console, SEARCH_TYPES, MAX_DISPLAY
from .helpers import fmt_dur, song_artists, song_album, song_dt, paged_slice
from .player import player
from .queue import queue


# ── search ──────────────────────────────────────────────────────────────────

def search_screen():
    console.clear()
    console.rule('[bold cyan]搜索[/bold cyan]')
    console.print()

    console.print('[bold]搜索类型:[/bold]')
    for k, (_, name) in SEARCH_TYPES.items():
        console.print(f'  [{k}] {name}')
    console.print()

    console.print('[dim]  [1-4] 选择类型  [回车] 返回[/dim]')
    st_in = Prompt.ask('类型', choices=list(SEARCH_TYPES.keys()), default='1')
    stype, stname = SEARCH_TYPES[st_in]
    console.print('[dim]  [关键词] 输入搜索词  [回车] 取消[/dim]')
    keyword = Prompt.ask('[bold]关键词[/bold]')
    if not keyword:
        return

    with console.status(f'[yellow]搜索 "{keyword}" ({stname})...'):
        try:
            result = apis.cloudsearch.getSearchResult(keyword, stype=stype, limit=30)
        except Exception as e:
            console.print(f'[red] 搜索失败: {e}[/red]')
            return

    if stype == apis.cloudsearch.SONG:
        handle_song_results(result)
    elif stype == apis.cloudsearch.ALBUM:
        handle_album_results(result)
    elif stype == apis.cloudsearch.ARTIST:
        handle_artist_results(result)
    elif stype == apis.cloudsearch.PLAYLIST:
        handle_playlist_results(result)


# ── search result handlers ──────────────────────────────────────────────────

def handle_song_results(result: dict):
    songs = result.get('result', {}).get('songs', [])
    if not songs:
        console.print('[yellow] 未找到结果[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    total = len(songs)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = songs[start:end]

        console.clear()
        console.rule('[bold cyan]搜索结果 (歌曲)[/bold cyan]')
        console.print()
        console.print(f'[bold]共 {total} 条[/bold]\n')
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌名', style='cyan')
        tbl.add_column('歌手', style='green')
        tbl.add_column('专辑', style='yellow')
        tbl.add_column('时长', style='dim')
        for i, s in enumerate(display, start + 1):
            tbl.add_row(str(i), s['name'], song_artists(s), song_album(s),
                         fmt_dur(song_dt(s)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[p]顺序播放全部')
        cmds.append('[d]下载全部')
        cmds.append('[pd]下载并播放')
        cmds.append('[序号]选曲')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        if choice == 'p':
            from .actions import playlist_play_all
            playlist_play_all(songs)
            return
        if choice == 'd':
            from .download import download_all_songs
            download_all_songs(songs)
            return
        if choice == 'pd':
            from .actions import play_all_with_download
            play_all_with_download(songs)
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                from .actions import song_action_menu
                song_action_menu(songs[idx])
                return
        except ValueError:
            pass


def handle_album_results(result: dict):
    albums = result.get('result', {}).get('albums', [])
    if not albums:
        console.print('[yellow] 未找到结果[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    total = len(albums)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = albums[start:end]

        console.clear()
        console.rule('[bold cyan]搜索结果 (专辑)[/bold cyan]')
        console.print()
        console.print(f'[bold]共 {total} 条[/bold]\n')
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('专辑', style='cyan')
        tbl.add_column('歌手', style='green')
        tbl.add_column('歌曲数', style='yellow')
        for i, a in enumerate(display, start + 1):
            ar = ', '.join((ar.get('name', '') or '') for ar in a.get('artists', []))
            tbl.add_row(str(i), a['name'], ar, str(a.get('size', '?')))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[序号]查看')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                album_detail(albums[idx])
                return
        except ValueError:
            pass


def handle_artist_results(result: dict):
    artists = result.get('result', {}).get('artists', [])
    if not artists:
        console.print('[yellow] 未找到结果[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    total = len(artists)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = artists[start:end]

        console.clear()
        console.rule('[bold cyan]搜索结果 (歌手)[/bold cyan]')
        console.print()
        console.print(f'[bold]共 {total} 条[/bold]\n')
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌手', style='cyan')
        tbl.add_column('专辑数', style='yellow')
        tbl.add_column('MV数', style='magenta')
        for i, a in enumerate(display, start + 1):
            tbl.add_row(str(i), a['name'], str(a.get('albumSize', 0)),
                         str(a.get('mvSize', 0)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[序号]查看')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                artist_detail(artists[idx])
                return
        except ValueError:
            pass


def handle_playlist_results(result: dict):
    playlists = result.get('result', {}).get('playlists', [])
    if not playlists:
        console.print('[yellow] 未找到结果[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    total = len(playlists)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = playlists[start:end]

        console.clear()
        console.rule('[bold cyan]搜索结果 (歌单)[/bold cyan]')
        console.print()
        console.print(f'[bold]共 {total} 条[/bold]\n')
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌单', style='cyan')
        tbl.add_column('作者', style='green')
        tbl.add_column('歌曲', style='yellow')
        tbl.add_column('播放', style='magenta')
        for i, p in enumerate(display, start + 1):
            tbl.add_row(str(i), p['name'],
                         p.get('creator', {}).get('nickname', '?'),
                         str(p.get('trackCount', 0)),
                         str(p.get('playCount', 0)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[序号]查看')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                playlist_detail(playlists[idx])
                return
        except ValueError:
            pass


# ── detail screens ──────────────────────────────────────────────────────────

def album_detail(album: dict):
    aid = album['id']
    with console.status('[yellow]获取专辑详情...'):
        try:
            info = apis.album.getAlbumInfo(aid)
        except Exception as e:
            console.print(f'[red] 获取失败: {e}[/red]')
            console.print()
            console.print('[dim]  [回车] 返回[/dim]')
            Prompt.ask('', default='')
            return

    al = info.get('album', info)
    songs = al.get('songs', [])
    if not songs:
        console.print('[yellow] 无歌曲数据[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    artists = ', '.join((a.get('name', '') or '') for a in al.get('artists', []))
    total = len(songs)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = songs[start:end]

        console.clear()
        console.rule(f'[bold cyan]专辑: {album["name"]}[/bold cyan]')
        console.print()
        console.print(f'[green]歌手:[/green] {artists}')
        console.print(f'[yellow]歌曲:[/yellow] {total}')
        console.print()
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌名', style='cyan')
        tbl.add_column('歌手', style='green')
        tbl.add_column('时长', style='dim')
        from .helpers import song_artists as fmt_artists
        for i, s in enumerate(display, start + 1):
            ar = fmt_artists(s)
            tbl.add_row(str(i), s['name'], ar, fmt_dur(s.get('dt', 0)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[p]顺序播放全部')
        cmds.append('[d]下载全部')
        cmds.append('[pd]下载并播放')
        cmds.append('[序号]选曲操作')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        if choice == 'p':
            from .actions import playlist_play_all
            playlist_play_all(songs)
            return
        if choice == 'd':
            from .download import download_all_songs
            download_all_songs(songs, subdir=album['name'])
            return
        if choice == 'pd':
            from .actions import play_all_with_download
            play_all_with_download(songs)
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                from .actions import song_action_menu
                song_action_menu(songs[idx], subdir=album['name'])
                return
        except ValueError:
            pass


def artist_detail(artist: dict):
    aid = artist['id']
    with console.status('[yellow]获取歌手歌曲...'):
        try:
            result = apis.artist.getArtistTracks(aid, limit=50)
        except Exception as e:
            console.print(f'[red] 获取失败: {e}[/red]')
            console.print()
            console.print('[dim]  [回车] 返回[/dim]')
            Prompt.ask('', default='')
            return

    songs = result.get('songs', [])
    if not songs:
        console.print('[yellow] 无歌曲数据[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    total = len(songs)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = songs[start:end]

        console.clear()
        console.rule(f'[bold cyan]歌手: {artist["name"]}[/bold cyan]')
        console.print()
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页 (共 {total} 首)[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌名', style='cyan')
        tbl.add_column('专辑', style='yellow')
        tbl.add_column('时长', style='dim')
        for i, s in enumerate(display, start + 1):
            tbl.add_row(str(i), s['name'], s.get('al', {}).get('name', '?'),
                         fmt_dur(s.get('dt', 0)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[p]顺序播放全部')
        cmds.append('[d]下载全部')
        cmds.append('[pd]下载并播放')
        cmds.append('[序号]选曲操作')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        if choice == 'p':
            from .actions import playlist_play_all
            playlist_play_all(songs)
            return
        if choice == 'd':
            from .download import download_all_songs
            download_all_songs(songs, subdir=artist['name'])
            return
        if choice == 'pd':
            from .actions import play_all_with_download
            play_all_with_download(songs)
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                from .actions import song_action_menu
                song_action_menu(songs[idx], subdir=artist['name'])
                return
        except ValueError:
            pass


def playlist_detail(playlist: dict):
    pid = playlist['id']
    with console.status('[yellow]获取歌单详情...'):
        try:
            tracks = apis.playlist.getPlaylistAllTracks(pid)
        except Exception as e:
            console.print(f'[red] 获取失败: {e}[/red]')
            console.print()
            console.print('[dim]  [回车] 返回[/dim]')
            Prompt.ask('', default='')
            return

    songs = tracks.get('songs', [])
    if not songs:
        console.print('[yellow] 无歌曲数据[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    creator = playlist.get('creator', {}).get('nickname', '?')
    total = len(songs)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = songs[start:end]

        console.clear()
        console.rule(f'[bold cyan]歌单: {playlist["name"]}[/bold cyan]')
        console.print()
        console.print(f'[green]作者:[/green] {creator}')
        console.print(f'[yellow]歌曲:[/yellow] {total}')
        console.print()
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌名', style='cyan')
        tbl.add_column('歌手', style='green')
        tbl.add_column('专辑', style='yellow')
        tbl.add_column('时长', style='dim')
        for i, s in enumerate(display, start + 1):
            ar = ', '.join((a.get('name', '') or '') for a in s.get('ar', []))
            al = s.get('al', {}).get('name', '?')
            tbl.add_row(str(i), s['name'], ar, al, fmt_dur(s.get('dt', 0)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[p]顺序播放全部')
        cmds.append('[d]下载全部')
        cmds.append('[pd]下载并播放')
        cmds.append('[序号]选曲操作')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        if choice == 'p':
            from .actions import playlist_play_all
            playlist_play_all(songs)
            return
        if choice == 'd':
            from .download import download_all_songs
            download_all_songs(songs, subdir=playlist['name'])
            return
        if choice == 'pd':
            from .actions import play_all_with_download
            play_all_with_download(songs)
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                from .actions import song_action_menu
                song_action_menu(songs[idx], subdir=playlist['name'])
                return
        except ValueError:
            pass


# ── my playlists ────────────────────────────────────────────────────────────

def _gather_all_playlist_songs(playlists: list) -> list:
    """收集所有歌单的全部歌曲"""
    from .apis import playlist as api_playlist
    all_songs = []
    with console.status('[yellow]收集歌单歌曲...'):
        for pl in playlists:
            try:
                tracks = api_playlist.getPlaylistAllTracks(pl['id'])
                all_songs.extend(tracks.get('songs', []))
            except Exception:
                pass
    return all_songs


def my_playlists_screen():
    console.clear()
    console.rule('[bold cyan]我的歌单[/bold cyan]')
    console.print()

    uid = getCurrentSession().uid
    if not uid:
        console.print('[red] 请先登录[/red]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    with console.status('[yellow]获取歌单...'):
        try:
            result = apis.user.getUserPlaylists(uid)
        except Exception as e:
            console.print(f'[red] 获取失败: {e}[/red]')
            console.print()
            console.print('[dim]  [回车] 返回[/dim]')
            Prompt.ask('', default='')
            return

    playlists = result.get('playlist', [])
    if not playlists:
        console.print('[yellow] 无歌单[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    total = len(playlists)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = playlists[start:end]

        console.clear()
        console.rule('[bold cyan]我的歌单[/bold cyan]')
        console.print()
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页 (共 {total} 个)[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌单', style='cyan')
        tbl.add_column('歌曲', style='yellow')
        tbl.add_column('播放', style='magenta')
        for i, p in enumerate(display, start + 1):
            tbl.add_row(str(i), p['name'], str(p.get('trackCount', 0)),
                         str(p.get('playCount', 0)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[p]顺序播放全部')
        cmds.append('[d]下载全部')
        cmds.append('[pd]下载并播放')
        cmds.append('[序号]查看')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        if choice == 'p':
            all_songs = _gather_all_playlist_songs(playlists)
            if all_songs:
                from .actions import playlist_play_all
                playlist_play_all(all_songs)
                return
            console.print('[red] 无可用歌曲[/red]')
            time.sleep(0.8)
            continue
        if choice == 'd':
            all_songs = _gather_all_playlist_songs(playlists)
            if all_songs:
                from .download import download_all_songs
                download_all_songs(all_songs)
                return
            console.print('[red] 无可用歌曲[/red]')
            time.sleep(0.8)
            continue
        if choice == 'pd':
            all_songs = _gather_all_playlist_songs(playlists)
            if all_songs:
                from .actions import play_all_with_download
                play_all_with_download(all_songs)
                return
            console.print('[red] 无可用歌曲[/red]')
            time.sleep(0.8)
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                playlist_detail(playlists[idx])
                return
        except ValueError:
            pass


# ── daily recommend ─────────────────────────────────────────────────────────

def daily_recommend_screen():
    console.clear()
    console.rule('[bold cyan]每日推荐[/bold cyan]')
    console.print()

    with console.status('[yellow]获取每日推荐...'):
        try:
            r = apis.user.getDailyRecommend()
        except Exception as e:
            console.print(f'[red] 获取失败: {e}[/red]')
            console.print()
            console.print('[dim]  [回车] 返回[/dim]')
            Prompt.ask('', default='')
            return

    songs = []
    raw = r.get('data', r)
    if isinstance(raw, dict):
        songs = raw.get('dailySongs', raw.get('songs', []))
    elif isinstance(raw, list):
        songs = raw

    if not songs:
        console.print('[yellow] 今日无推荐[/yellow]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    total = len(songs)
    page = 0

    while True:
        start, end, pages = paged_slice(total, page)
        display = songs[start:end]

        console.clear()
        console.rule('[bold cyan]每日推荐[/bold cyan]')
        console.print()
        console.print(f'[bold]今日推荐: {total} 首[/bold]\n')
        if pages > 1:
            console.print(f'[dim]  第 {page+1}/{pages} 页[/dim]')

        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column('#', style='dim', width=3)
        tbl.add_column('歌名', style='cyan')
        tbl.add_column('歌手', style='green')
        tbl.add_column('专辑', style='yellow')
        tbl.add_column('时长', style='dim')
        for i, s in enumerate(display, start + 1):
            tbl.add_row(str(i), s['name'], song_artists(s), song_album(s),
                         fmt_dur(song_dt(s)))
        console.print(tbl)
        console.print()

        cmds = []
        if pages > 1:
            if page > 0: cmds.append('[b]上页')
            if page < pages - 1: cmds.append('[n]下页')
        cmds.append('[p]顺序播放全部')
        cmds.append('[d]下载全部')
        cmds.append('[pd]下载并播放')
        cmds.append('[序号]选曲操作')
        cmds.append('[回车]返回')
        console.print('  ' + escape('  '.join(cmds)))
        console.print()

        choice = Prompt.ask('[bold]选择[/bold]', default='').strip()
        if not choice:
            return
        if choice == 'n' and page < pages - 1:
            page += 1
            continue
        if choice == 'b' and page > 0:
            page -= 1
            continue
        if choice == 'p':
            from .actions import playlist_play_all
            playlist_play_all(songs)
            return
        if choice == 'd':
            from .download import download_all_songs
            download_all_songs(songs, subdir='每日推荐')
            return
        if choice == 'pd':
            from .actions import play_all_with_download
            play_all_with_download(songs)
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < total:
                from .actions import song_action_menu
                song_action_menu(songs[idx], subdir='每日推荐')
                return
        except ValueError:
            pass


# ── user profile ────────────────────────────────────────────────────────────

def user_profile_screen():
    console.clear()
    console.rule('[bold cyan]用户信息[/bold cyan]')
    console.print()

    s = getCurrentSession()
    if not s.logged_in:
        console.print('[red] 未登录[/red]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    vt = {0: '无', 1: '普通VIP', 2: '音乐包'}
    console.print(f'[bold]UID:[/bold] {s.uid}')
    console.print(f'[bold]昵称:[/bold] {s.nickname}')
    console.print(f'[bold]VIP:[/bold] {vt.get(s.vipType, "未知")}')
    console.print(f'[bold]上次登录IP:[/bold] {s.lastIP}')

    bindings = s.bindings
    if bindings:
        console.print()
        console.print('[bold]绑定:[/bold]')
        for b in bindings:
            console.print(f'  {b.get("type", 0)}: {b.get("userId", "?")}')

    console.print()
    console.print('[dim]  [回车] 返回[/dim]')
    Prompt.ask('', default='')


# ── lyrics query screen ─────────────────────────────────────────────────────

def lyrics_screen():
    console.clear()
    console.rule('[bold cyan]歌词查询[/bold cyan]')
    console.print()

    console.print('[dim]  [歌曲ID] 输入ID  [回车] 返回[/dim]')
    sid_str = Prompt.ask('[bold]歌曲ID[/bold]')
    if not sid_str:
        return
    try:
        sid = int(sid_str)
    except ValueError:
        console.print('[red] 无效ID[/red]')
        console.print()
        console.print('[dim]  [回车] 返回[/dim]')
        Prompt.ask('', default='')
        return

    from .lyrics import show_lyrics
    show_lyrics(sid)


# ── signin ──────────────────────────────────────────────────────────────────

def signin_screen():
    console.clear()
    console.rule('[bold cyan]每日签到[/bold cyan]')
    console.print()

    with console.status('[yellow]签到中...'):
        try:
            r = apis.user.setSignin(dtype=apis.user.SIGNIN_TYPE_MOBILE)
            if r.get('code') == 200:
                console.print('[green] 手机端签到成功 (+4 exp)[/green]')
            else:
                console.print(f'[yellow] 手机端: {r}[/yellow]')
        except Exception as e:
            console.print(f'[red] 签到失败: {e}[/red]')

    console.print()
    console.print('[dim]  [回车] 返回[/dim]')
    Prompt.ask('', default='')
