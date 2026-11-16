"""Preview or apply waveform-verified official titles; preserve current names."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from pipeline_paths import REPOSITORY, GAME, protect_output


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def official_name(official, current):
    if current == official or (current.startswith(official+'（') and current.endswith('）')):
        return current
    return official+'（'+current+'）'


def verified_matches(report):
    result = {}
    for match in report['matches']:
        evidence = match['evidence']
        good = [c for c in evidence.get('waveform_checks', []) if c['correlation'] >= .9]
        if not evidence.get('verified') or evidence.get('waveform_median', 0) < .92 or len(good) < 2:
            raise ValueError('Refusing unverified official name: '+match['audio_id'])
        result[match['audio_id']] = match
    return result


def renamed(stories, outfits, report):
    stories, outfits = copy.deepcopy(stories), copy.deepcopy(outfits)
    matches, changes = verified_matches(report), []
    by_file = {'/audio/'+identifier+'.opus': match for identifier, match in matches.items()}
    for group in stories['groups']:
        for track in group['tracks']:
            match = by_file.get(track['file'])
            if not match:
                continue
            current = track['name']; title = official_name(match['official_title'], current)
            if title != current:
                track['name'] = title
                changes.append({'scope': 'story', 'group_id': group['id'], 'file': track['file'],
                                'old_name': current, 'name': title, 'audio_id': match['audio_id'],
                                'qq_mid': match['qq_mid'], 'official_title': match['official_title']})
    for outfit in outfits['items']:
        for track in outfit['music']:
            match = matches.get(track['id'])
            if not match:
                continue
            # Core/victory are functional game UI labels; the recording's name
            # is the disc name. A distinct official name appears in the player.
            current = track.get('display_title') or outfit['name']
            title = official_name(match['official_title'], current)
            if title != current:
                track['display_title'] = title
                changes.append({'scope': 'outfit', 'outfit_id': outfit['id'], 'variant': track['title'],
                                'old_name': current, 'name': title, 'audio_id': match['audio_id'],
                                'qq_mid': match['qq_mid'], 'official_title': match['official_title']})
    return stories, outfits, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matches', type=Path, default=REPOSITORY/'references/qqmusic-matches.json')
    parser.add_argument('--mapping', type=Path, default=REPOSITORY/'public/data/story-melodies.json')
    parser.add_argument('--outfits', type=Path, default=REPOSITORY/'public/data/outfits.json')
    parser.add_argument('--report', type=Path, default=REPOSITORY/'.build/qqmusic/name-changes.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--restore-cookie', action='store_true', help='Restore short Cookie cues in the same mapping update.')
    parser.add_argument('--audio-root', type=Path, default=REPOSITORY)
    parser.add_argument('--render-catalog', type=Path, default=REPOSITORY/'.build/import/catalog.json')
    args = parser.parse_args()
    for path in [args.mapping, args.outfits, args.report]:
        protect_output(path, GAME)
    metadata_path = REPOSITORY/'public/data/library.json'
    paths = [args.mapping, args.outfits]+([metadata_path] if args.restore_cookie else [])
    original = {path: path.read_bytes() for path in paths}
    stories = read(args.mapping)
    restored = []
    if args.restore_cookie:
        from restore_cookie_music import restore
        stories, metadata, restored = restore(stories, read(metadata_path), read(REPOSITORY/'references/analysis/content_groups.json'))
    stories, outfits, changes = renamed(stories, read(args.outfits), read(args.matches))
    report = {'schema_version': 1, 'changes': changes,
              'source_mapping_sha256': hashlib.sha256(original[args.mapping]).hexdigest(),
              'name_format': 'official title（previous current title）',
              'policy': 'Verified names only; optional explicit Cookie short-cue restoration. Existing descriptions, dates, file paths and game core/victory labels are preserved.',
              'restored_cookie': [{'audio_id': c['id'], 'name': c['title'], 'duration_seconds': c['duration_seconds']} for c in restored]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    if args.apply:
        if args.restore_cookie:
            from restore_cookie_music import prepare_audio
            prepare_audio(restored, REPOSITORY, args.audio_root, args.render_catalog)
        # Re-read immediately before writing: never replace edits made while the
        # proposal was calculated. Old buffers must still be reloaded by editors.
        if any(path.read_bytes() != contents for path, contents in original.items()):
            raise SystemExit('Files changed concurrently; nothing applied. Re-run preview from saved files.')
        backup = REPOSITORY/'.build/qqmusic/backups'/hashlib.sha256(original[args.mapping]).hexdigest()[:16]
        backup.mkdir(parents=True, exist_ok=True)
        updates = [(args.mapping, stories), (args.outfits, outfits)]+([(metadata_path, metadata)] if args.restore_cookie else [])
        for path, value in updates:
            (backup/path.name).write_bytes(original[path])
            temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8'); temp.replace(path)
    print(f'Verified name changes: {len(changes)}; applied: {args.apply}; report: {args.report}')


if __name__ == '__main__':
    main()
