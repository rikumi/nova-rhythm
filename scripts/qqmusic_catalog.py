"""Read QQ Music's public artist catalog and cache available playback audio.

No cookies, signatures, paywall workarounds or third-party music proxies. Audio
and expiring URLs stay in ignored work directories; only metadata is publishable.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

from pipeline_paths import REPOSITORY, GAME, protect_output

API = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
ARTIST_MID = '001Rt7AK0ImjcV'
HEADERS = {'Referer': 'https://y.qq.com/', 'User-Agent': 'Mozilla/5.0'}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    temp.replace(path)


def request(modules):
    payload = {'comm': {'ct': 24, 'cv': 4747474, 'format': 'json', 'platform': 'yqq.json', 'uin': 0}, **modules}
    url = API+'?'+urllib.parse.urlencode({'data': json.dumps(payload, ensure_ascii=False)})
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as response:
        result = json.load(response)
    if result.get('code') != 0:
        raise RuntimeError(f'QQ Music response code: {result.get("code")}')
    for key in modules:
        if result.get(key, {}).get('code') != 0:
            raise RuntimeError(f'QQ Music {key} response code: {result.get(key, {}).get("code")}')
    return {key: result[key]['data'] for key in modules}


def artist_songs(mid):
    songs, total, begin = {}, None, 0
    while total is None or begin < total:
        result = request({'songs': {'module': 'musichall.song_list_server', 'method': 'GetSingerSongList',
                                   'param': {'singerMid': mid, 'begin': begin, 'num': 100, 'order': 1}}})['songs']
        total = result['totalNum']; page = result['songList']
        if not page and begin < total:
            raise RuntimeError('Artist pagination stopped before advertised total')
        for item in page:
            song = item['songInfo']
            if not any(singer['mid'] == mid for singer in song.get('singer', [])):
                raise ValueError('Unexpected artist in song listing')
            songs[song['mid']] = song
        begin += len(page)
    if len(songs) != total:
        raise RuntimeError(f'Artist catalog inconsistent: {len(songs)} unique songs / {total} advertised')
    return list(songs.values()), total


def public_song(song):
    return {'id': song['id'], 'mid': song['mid'], 'title': song.get('title') or song['name'],
            'subtitle': song.get('subtitle', ''), 'duration_seconds': song['interval'],
            'artists': [{k: singer[k] for k in ['id', 'mid', 'name']} for singer in song['singer']],
            'album': {k: song['album'].get(k) for k in ['id', 'mid', 'name', 'time_public']},
            'publish_date': song.get('time_public', ''),
            'url': 'https://y.qq.com/n/ryqq_v2/songDetail/'+song['mid'],
            'media_mid': song['file']['media_mid'],
            'expected_mp3_bytes': song['file'].get('size_128mp3', 0),
            'play_requires_payment': bool(song.get('pay', {}).get('pay_play'))}


def download(song, url, work):
    path = work/'audio'/(song['mid']+'.mp3'); path.parent.mkdir(parents=True, exist_ok=True)
    expected = song['expected_mp3_bytes']
    try:
        if path.is_file() and path.stat().st_size > 1000 and (not expected or path.stat().st_size == expected):
            return {'mid': song['mid'], 'status': 'cached', 'file': str(path.relative_to(work)),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}
        if not url:
            return {'mid': song['mid'], 'status': 'unavailable_without_login'}
        host = urllib.parse.urlparse(url).hostname or ''
        if not host.endswith('.qq.com'):
            raise ValueError('Unexpected audio host')
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=90) as response:
            data = response.read()
            length = response.headers.get('Content-Length')
        if len(data) < 1000 or (length and len(data) != int(length)):
            raise ValueError('Incomplete audio response')
        if expected and len(data) != expected:
            raise ValueError(f'Unexpected audio size: {len(data)} / {expected}')
        temp = path.with_suffix('.tmp'); temp.write_bytes(data); temp.replace(path)
        return {'mid': song['mid'], 'status': 'downloaded', 'file': str(path.relative_to(work)),
                'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    except Exception as exc:
        return {'mid': song['mid'], 'status': 'failed', 'error': str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artist-mid', default=ARTIST_MID)
    parser.add_argument('--work-dir', type=Path, default=REPOSITORY/'.build/qqmusic')
    parser.add_argument('--catalog', type=Path, default=REPOSITORY/'references/qqmusic-catalog.json')
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    work = protect_output(args.work_dir, GAME); protect_output(args.catalog, GAME)
    songs, total = artist_songs(args.artist_mid)
    catalog = {'schema_version': 1, 'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'artist': {'name': '星塔唱片', 'mid': args.artist_mid,
                          'url': 'https://y.qq.com/n/ryqq_v2/singer/'+args.artist_mid},
               'api': API, 'catalog_method': 'musichall.song_list_server.GetSingerSongList',
               'advertised_total': total, 'unique_total': len(songs),
               'songs': [public_song(song) for song in songs]}
    save(args.catalog, catalog)
    print(f'Artist catalog complete: {len(songs)}/{total} songs; {len({s["album"]["mid"] for s in songs})} albums', flush=True)
    if not args.download:
        return
    urls = {}
    for begin in range(0, len(songs), 20):
        batch = songs[begin:begin+20]
        result = request({'vkey': {'module': 'vkey.GetVkeyServer', 'method': 'CgiGetVkey',
                                  'param': {'guid': '1829357182', 'songmid': [s['mid'] for s in batch],
                                            'songtype': [s['type'] for s in batch], 'uin': '0', 'loginflag': 1, 'platform': '20',
                                            'filename': ['M500'+s['file']['media_mid']+'.mp3' for s in batch]}}})['vkey']
        base = next((sip for sip in result.get('sip', []) if sip.startswith('https://')), result.get('sip', [''])[0])
        for item in result.get('midurlinfo', []):
            if item.get('purl'):
                urls[item['songmid']] = urllib.parse.urljoin(base, item['purl'])
        time.sleep(.15)
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(download, song, urls.get(song['mid']), work) for song in catalog['songs']]
        for future in as_completed(futures):
            result = future.result(); results.append(result)
            if len(results) % 20 == 0 or result['status'] not in ['downloaded', 'cached']:
                print(f'{len(results)}/{total}: {result["status"]}', flush=True)
    save(work/'downloads.json', {'catalog': str(args.catalog), 'downloads': results})
    good = sum(r['status'] in ['downloaded', 'cached'] for r in results)
    print(f'Available full playback audio downloaded: {good}/{total}', flush=True)
    if good != total:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
