"""Fetch pinned community config/Lua mirrors into an isolated research workspace."""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pipeline_paths import GAME, REPOSITORY, protect_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, default=REPOSITORY/'.build/analysis')
    parser.add_argument('--only', choices=['tables', 'lua', 'all'], default='all')
    args = parser.parse_args()
    work = protect_output(args.work_dir, GAME)
    sources = json.loads((REPOSITORY/'references/sources.json').read_text(encoding='utf8'))
    for source in sources['mirrors']:
        if args.only not in ['all', source['folder']]:
            continue
        # archive_root was captured at original download; no unpinned "latest".
        commit = source['archive_root'].rstrip('/').rsplit('-', 1)[1]
        if not re.fullmatch(r'[0-9a-f]{7,40}', commit):
            raise ValueError('Invalid source revision')
        url = f'https://api.github.com/repos/{source["repo"]}/zipball/{commit}'
        dest = work/'data/upstream'/source['folder']
        print(url, flush=True)
        with tempfile.TemporaryFile() as temp:
            request = urllib.request.Request(url, headers={'User-Agent': 'nova-rhythm-research'})
            with urllib.request.urlopen(request, timeout=120) as response:
                shutil.copyfileobj(response, temp)
            temp.seek(0)
            with zipfile.ZipFile(temp) as archive:
                root = archive.namelist()[0]
                for info in archive.infolist():
                    relative = info.filename[len(root):]
                    if info.is_dir() or (source['folder'] == 'tables' and not relative.startswith('CN/')):
                        continue
                    target = (dest/relative).resolve()
                    if not target.is_relative_to(dest.resolve()):
                        raise ValueError('Unsafe archive path')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as src, target.open('wb') as out:
                        shutil.copyfileobj(src, out)
        (dest/'source.json').write_text(json.dumps(source, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
