"""Identify activity shop discs and remove identical activity background music.

Only the editable story mapping and review report are written. Audio and game
resources are never changed. Lossy website Opus is never used for comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from pipeline_paths import REPOSITORY, protect_output, GAME
from story_mapping import apply_mapping


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def shop_evidence(tables, outfits, mapping):
    read = lambda name: load(tables/(name+'.json'))
    groups, controls, goods, discs = (read(n) for n in ['ActivityGroup', 'ActivityShopControl', 'ActivityGoods', 'DiscIP'])
    by_item = {int(d['Id']): d for d in discs.values()}
    by_id = {o['id']: o for o in outfits['items']}
    names = {g['id']: g['name'] for g in mapping['groups']}
    entries = []
    for group in groups.values():
        store = json.loads(group.get('Enter', '{}')).get('Store', [])
        control = controls.get(str(store[0]), {}) if store else {}
        shops = control.get('ShopIds', [])
        matches = [g for g in goods.values() if g['ShopId'] in shops and g['ItemId'] in by_item]
        candidates = []
        for item_id in sorted({g['ItemId'] for g in matches}):
            disc, outfit = by_item[item_id], by_id.get(item_id, {})
            candidates.append({'outfit_id': item_id, 'code': disc['VoFile'].split('_')[-1],
                               'name': outfit.get('name', disc['VoFile']),
                               'goods': [g for g in matches if g['ItemId'] == item_id]})
        entries.append({'group_id': 'activity-'+str(group['Id']), 'activity_id': group['Id'],
                        'name': names.get('activity-'+str(group['Id']), 'activity-'+str(group['Id'])),
                        'date': group.get('StartTime', ''), 'store_entry': store,
                        'shop_control': control, 'candidates': candidates,
                        'status': 'unique_shop_outfit' if len(candidates) == 1 else 'ambiguous' if candidates else 'no_shop_outfit'})
    hashes = {n: hashlib.sha256((tables/(n+'.json')).read_bytes()).hexdigest()
              for n in ['ActivityGroup', 'ActivityShopControl', 'ActivityGoods', 'DiscIP']}
    return {'schema_version': 1, 'basis': 'ActivityGroup.Enter.Store -> ActivityShopControl.ShopIds -> ActivityGoods.ItemId -> DiscIP',
            'source_table_sha256': hashes, 'entries': entries}


def compare(evidence, mapping, library, outfits, contents, locate, prefix_hash):
    by_group = {g['id']: g for g in mapping['groups']}
    by_file = {t['path']: t for t in library['tracks']}
    by_outfit = {o['id']: o for o in outfits['items']}
    by_content = {c['id']: c for c in contents['contents']}
    decisions, activities, errors = [], [], []
    for event in evidence['entries']:
        result = {'group_id': event['group_id'], 'name': event['name'], 'shop_status': event['status'], 'comparisons': []}
        activities.append(result)
        if event['status'] != 'unique_shop_outfit':
            continue
        main = event['candidates'][0]
        result['main_outfit'] = {k: main[k] for k in ['outfit_id', 'code', 'name']}
        outfit = by_outfit.get(main['outfit_id'])
        core = next((m for m in outfit['music'] if m['title'] == '核心旋律'), None) if outfit else None
        if not core:
            result['status'] = 'missing_core_melody'; continue
        result['main_audio_id'] = core['id']
        result['main_core_has_system_alias'] = 'system' in by_content.get(core['id'], {}).get('categories', [])
        group = by_group.get(event['group_id'])
        if not group:
            result['status'] = 'no_displayed_group'; continue
        for entry in list(group.get('tracks', [])):
            track = by_file.get(entry['file'])
            content = by_content.get(track['id']) if track else None
            # Limit removals to source-proven system/background music, preserving
            # unrelated combat arrangements and story cues in the same event.
            if not content or 'system' not in content.get('categories', []):
                continue
            comparison = {'audio_id': track['id'], 'name': entry['name'], 'file': entry['file'],
                          'main_audio_id': core['id'], 'match': None}
            result['comparisons'].append(comparison)
            if track['id'] == core['id']:
                comparison['match'] = 'identical_full_pcm'
            elif min(track['duration_seconds'], core['duration_seconds']) >= 60:
                try:
                    left, right = locate(track['id']), locate(core['id'])
                    comparison.update(activity_prefix_sha256=prefix_hash(left), main_prefix_sha256=prefix_hash(right))
                    if comparison['activity_prefix_sha256'] == comparison['main_prefix_sha256']:
                        comparison['match'] = 'identical_first_60_seconds_pcm'
                except Exception as exc:
                    errors.append({'group_id': event['group_id'], 'audio_id': track['id'], 'error': str(exc)})
            else:
                comparison['status'] = 'less_than_60_seconds'
            if comparison['match']:
                decisions.append({'group_id': event['group_id'], 'group_name': group['name'],
                                  'main_outfit': result['main_outfit'], **comparison,
                                  'removed_entry': dict(entry)})
    return {'schema_version': 1,
            'comparison': 'Decoded lossless FLAC, normalized stereo 44100 Hz signed PCM16; exact first 60 seconds SHA-256, or full PCM identity',
            'policy': 'Unique exchangeable outfit in the activity shop; only source-proven system BGM; core melody only, no lossy Opus comparisons',
            'activities': activities, 'removed': decisions, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, default=REPOSITORY/'public/data/story-melodies.json')
    parser.add_argument('--evidence', type=Path, default=REPOSITORY/'references/activity-main-outfits.json')
    parser.add_argument('--tables-dir', type=Path, help='Refresh shop evidence from mirrored CN/bin tables.')
    parser.add_argument('--render-catalog', type=Path, default=REPOSITORY/'.build/import/catalog.json')
    parser.add_argument('--audio-root', type=Path, default=REPOSITORY, help='Workspace containing lossless music/ exports.')
    parser.add_argument('--report', type=Path, default=REPOSITORY/'.build/activity-theme-dedup.json')
    parser.add_argument('--apply', action='store_true', help='Remove verified matches from the editable mapping.')
    args = parser.parse_args()
    for target in [args.mapping, args.evidence, args.report]:
        protect_output(target, GAME)
    mapping = load(args.mapping)
    metadata = load(REPOSITORY/'public/data/library.json')
    library = apply_mapping(mapping, metadata)
    outfits = load(REPOSITORY/'public/data/outfits.json')
    if args.tables_dir:
        evidence = shop_evidence(args.tables_dir, outfits, mapping)
        save(args.evidence, evidence)
    else:
        evidence = load(args.evidence)
    contents = load(REPOSITORY/'references/analysis/content_groups.json')
    paths = {c['id']: args.audio_root/c['path'].lstrip('/') for c in contents['contents']}
    if args.render_catalog.exists():
        for row in load(args.render_catalog)['tracks']:
            if row.get('status') == 'exported':
                paths['audio-'+row['pcm_sha256']] = args.render_catalog.parent/f'lossless/{row["render_key"]}.flac'
    def locate(identifier):
        path = paths.get(identifier)
        if not path or not path.is_file() or path.suffix.lower() != '.flac':
            raise FileNotFoundError(f'Missing lossless export for {identifier}; render game audio first.')
        return path
    import imageio_ffmpeg
    ffmpeg, cache = imageio_ffmpeg.get_ffmpeg_exe(), {}
    def prefix_hash(path):
        if path not in cache:
            result = subprocess.run([ffmpeg, '-v', 'error', '-i', str(path), '-t', '60', '-ac', '2', '-ar', '44100',
                                     '-c:a', 'pcm_s16le', '-f', 'hash', '-hash', 'sha256', '-'], capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError(result.stderr)
            cache[path] = result.stdout.strip().split('=')[-1]
        return cache[path]
    report = compare(evidence, mapping, library, outfits, contents, locate, prefix_hash)
    save(args.report, report)
    if args.apply:
        if report['errors']:
            raise SystemExit('Comparison errors; mapping left unchanged. Inspect report.')
        removed = {(r['group_id'], r['file']) for r in report['removed']}
        for group in mapping['groups']:
            group['tracks'] = [t for t in group['tracks'] if (group['id'], t['file']) not in removed]
        save(args.mapping, mapping)
    print(f'Activities: {len(report["activities"])}; verified removals: {len(report["removed"])}; errors: {len(report["errors"])}')
    print(f'Report: {args.report}')
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
