"""Package local analysis as portable reference data, without caches or binaries.

Run only after deliberately reviewing an updated analysis. Does not read Telegram
audio or write any game files. The normal incremental importer never runs this.
"""
import hashlib
import json
import re
from pathlib import Path
from pipeline_paths import ROOT, GAME, REPOSITORY


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def portable(value):
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items() if k != 'mtime_ns'}
    if isinstance(value, list):
        return [portable(v) for v in value]
    if isinstance(value, str):
        for base, token in [(GAME, '{{GAME}}'), (ROOT, '{{WORK}}')]:
            value = value.replace(str(base), token).replace(base.as_posix(), token)
        return value
    return value


def main():
    dest = REPOSITORY/'references'
    inventory = load(ROOT/'data/inventory.json')['entries']
    rows = inventory + load(ROOT/'data/supplemental_inventory.json') + load(ROOT/'data/audio_variants.json')
    entries = []
    for row in rows:
        entry = portable({k: v for k, v in row.items() if k not in ['path', 'recipe', 'dependencies', 'size']})
        if row.get('recipe'):
            lines = []
            for line in row['recipe'].splitlines():
                if line.lstrip().startswith('#'):
                    lines.append(portable(line)); continue
                match = re.match(r'^(\s*)(.*?\.(?:wem|bnk))(?=\s|$)(.*)$', line)
                if match:
                    source = (Path(row['path']).parent/match[2]).resolve()
                    if not source.exists() and source.suffix.lower() == '.bnk':
                        source = source.parent.parent/source.name
                    rel = source.relative_to(GAME).as_posix()
                    line = match[1]+'{{GAME}}/'+rel+match[3]
                lines.append(portable(line))
            recipe = '\n'.join(lines)+'\n'
            filename = f'txtp/{row["source"]}/{row["id"]}.txtp'
            p = dest/filename; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(recipe, encoding='utf8', newline='\n')
            entry['recipe_file'] = filename
            entry['recipe_sha256'] = hashlib.sha256(recipe.encode()).hexdigest()
        entries.append(entry)
    save(dest/'routes.json', {'schema_version': 1, 'game_token': '{{GAME}}', 'entries': entries})
    names = [
        'catalog', 'content_groups', 'fields', 'music_localization', 'library_catalog',
        'outfit_activity_order', 'story_music_calls', 'config_music_usages',
        'lua_music_states', 'wwise_event_states', 'wwise_hash_names', 'wwise_objects',
        'unity_audio_usages', 'card_motion', 'native_hardware_story',
        'phonograph_hardware', 'native_melody_buttons', 'native_note_texture',
        'story_button_slicing', 'home_native_icons', 'web_runtime_assets',
        'ui_wanted_sprites', 'zombie_name_verification', 'artwork',
    ]
    for name in names:
        save(dest/f'analysis/{name}.json', portable(load(ROOT/f'data/{name}.json')))
    # Filename clues only; discard personal paths, timestamps and download metadata.
    if (ROOT/'data/reference_names.json').exists():
        hints = load(ROOT/'data/reference_names.json')
        save(dest/'name_hints.json', {
            'channel': hints['channel'], 'policy': hints['policy'],
            'entries': [{k: row.get(k) for k in ['filename', 'disc_id', 'naming_hint', 'evidence', 'reference_only']}
                        for row in hints['entries']],
        })
    contents = load(ROOT/'data/content_groups.json')['contents']
    published = {p.stem for p in (REPOSITORY/'public/audio').glob('*.opus')}
    save(dest/'selection.json', {
        'schema_version': 1, 'identity': 'decoded PCM SHA-256, not encoded Opus bytes',
        'policy': {'exclude_transition': True, 'library_minimum_seconds': 60,
                   'primary_owner_priority': ['outfit', 'system', 'combat', 'story'],
                   'outfit_reference': 'first release activity only'},
        'contents': [{k: c[k] for k in ['id', 'pcm_sha256', 'category', 'route_ids']} |
                     {'selected': c['id'] in published} for c in contents],
    })
    save(dest/'sources.json', {
        'schema_version': 1,
        'mirrors': [dict(load(ROOT/f'data/upstream/{folder}/source.json'), folder=folder)
                    for folder in ['tables', 'lua']],
        'note': 'Mirrors assist naming; they are not verified byte-identical to local encrypted game tables.',
    })
    print(f'Packaged {len(entries)} routes, {len(published)} selected audio identities.')


if __name__ == '__main__':
    main()
