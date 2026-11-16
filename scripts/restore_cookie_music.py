"""Restore short Sweet Dream Workshop cues from the already analyzed PCM catalog."""
import copy
import json
from pathlib import Path
import subprocess

COOKIE_GROUP = 'mode-甜心梦工坊'


def is_cookie(content):
    return any(str(state.get('value', '')).lower().startswith('cookie') or str(state.get('group', '')).lower() == 'cookie'
               for state in content.get('source_states', []))


def restore(mapping, metadata, contents):
    mapping, metadata = copy.deepcopy(mapping), copy.deepcopy(metadata)
    group = next((g for g in mapping['groups'] if g['id'] == COOKIE_GROUP), None)
    technical_group = next(g for g in metadata['groups'] if g['id'] == COOKIE_GROUP)
    if group is None:
        group = {'id': COOKIE_GROUP, 'name': '甜心梦工坊', 'date': technical_group.get('date', ''),
                 'description': '', 'outfit_references': [], 'tracks': []}
        mapping['groups'].append(group)
    group['minimum_duration_seconds'] = 0
    present = {t['file'] for g in mapping['groups'] for t in g['tracks']}
    indexed = {t['id'] for t in metadata['tracks']}
    restored = []
    for content in contents['contents']:
        if content['category'] == 'outfit' or not is_cookie(content) or content['duration_seconds'] >= 60:
            continue
        file = '/audio/'+content['id']+'.opus'
        if file in present:
            continue
        group['tracks'].append({'id': content['id'], 'name': content['title'], 'file': file, 'description': ''})
        restored.append(content)
        present.add(file)
        if content['id'] not in indexed:
            fields = ['id', 'sample_rate', 'channels', 'number_of_samples', 'duration_seconds', 'loop']
            metadata['tracks'].append({**{k: content[k] for k in fields}, 'title': content['title'], 'path': file,
                                       'group_id': COOKIE_GROUP, 'source_title': content['title'],
                                       'uses': content.get('uses', []), 'aliases': content.get('aliases', [])})
            indexed.add(content['id'])
            technical_group['track_ids'].append(content['id'])
    return mapping, metadata, restored


def prepare_audio(contents, repository, audio_root, render_catalog):
    import imageio_ffmpeg
    paths = {c['id']: audio_root/c['path'].lstrip('/') for c in contents}
    if render_catalog.exists():
        data = json.loads(render_catalog.read_text(encoding='utf8'))
        for row in data['tracks']:
            candidate = render_catalog.parent/f'lossless/{row.get("render_key")}.flac'
            if row.get('status') == 'exported' and candidate.is_file():
                paths['audio-'+row['pcm_sha256']] = candidate
    for content in contents:
        target = repository/f'public/audio/{content["id"]}.opus'
        if target.exists():
            continue
        source = paths[content['id']]
        if not source.is_file():
            raise FileNotFoundError(f'Render the lossless game audio first: {content["id"]}')
        temporary = target.with_suffix('.tmp.opus')
        result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(source),
                                 '-vn', '-map_metadata', '-1', '-c:a', 'libopus', '-b:a', '160k', '-vbr', 'on',
                                 '-compression_level', '10', '-frame_duration', '20', '-ar', '48000', '-threads', '1', str(temporary)], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf8', errors='replace'))
        temporary.replace(target)
