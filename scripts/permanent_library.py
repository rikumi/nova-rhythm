"""Classify curated music using game states and verified floor BGM references."""
import copy

ANCHOR = 'permanent-combat'
PERMANENT_NAMES = ['星塔探索', '心危擂台', '真格挑战', '灾变防线', '猎影合围', '尖兵陷阵', '联合讨伐', '巅峰秀场', '晋升试炼']
PERMANENT_IDS = ['mode-'+name for name in PERMANENT_NAMES]
TABLE_MODES = {'WeekBossFloor': '真格挑战', 'ScoreBossFloor': '联合讨伐', 'TraceHuntFloor': '猎影合围',
               'SoldierFloor': '尖兵陷阵', 'TravelerDuelFloor': '巅峰秀场', 'TravelerDuelLevel': '巅峰秀场', 'RegionBossFloor': '晋升试炼'}


def mode_candidates(entry, current_group, content, routes):
    reasons = {}
    def add(name, reason):
        reasons.setdefault('mode-'+name, []).append(reason)
    title = entry['name'].split('（', 1)[0].strip()
    if any(title.startswith(name) for name in ['流水与暗影', '风暴与闪电', '烈焰与尘埃']):
        add('星塔探索', 'User specified exploration theme family')
    for state in content.get('source_states', []):
        group, value = str(state.get('group', '')).lower(), str(state.get('value', '')).lower()
        if (group in ['level', 'system'] and value == 'endlesstower'):
            add('心危擂台', f'Wwise {group}={value}')
        if group in ['level', 'system'] and value.startswith('zombie'):
            add('灾变防线', f'Wwise {group}={value}')
        if group in ['level', 'system'] and value.startswith('zizou'):
            add('尖兵陷阵', f'Wwise {group}={value}')
        if group == 'system' and value in ['lieying', 'groupcombat']:
            add('猎影合围', f'Wwise {group}={value}')
        if group == 'system' and value == 'bossrank':
            add('真格挑战', 'WeeklyCopies UI bossRank audio / WeekBoss gameplay')
        if (group == 'level' and value == 'travelerduel') or (group == 'system' and value == 'duel'):
            add('巅峰秀场', f'Wwise {group}={value}; UIText.LevelMenu_TravelerDuel')
        if group == 'system' and value == 'regionboss':
            add('晋升试炼', 'Wwise system=regionBoss; UIText.LevelMenu_Region')
    for route in routes:
        for use in route.get('config_usages', []):
            if use.get('match') == 'all_recipe_fields' and use.get('table') in TABLE_MODES:
                add(TABLE_MODES[use['table']], f'{use["table"]}:{use["id"]} BGM={use["event"]}')
    if current_group in PERMANENT_IDS:
        reasons.setdefault(current_group, []).append('Existing curated permanent gameplay group')
    if 'mode-星塔探索' in reasons:
        selected = 'mode-星塔探索'
    elif current_group in reasons:
        selected = current_group
    else:
        selected = next((identifier for identifier in PERMANENT_IDS if identifier in reasons), None)
    return selected, reasons


def reorganize(mapping, metadata, contents, catalog):
    result = copy.deepcopy(mapping)
    by_file = {track['path']: track for track in metadata['tracks']}
    by_content = {content['id']: content for content in contents['contents']}
    by_route = {route['id']: route for route in catalog['tracks']}
    groups = {group['id']: group for group in result['groups']}
    for identifier, name in zip(PERMANENT_IDS, PERMANENT_NAMES):
        groups.setdefault(identifier, {'id': identifier, 'name': name, 'date': '', 'description': '', 'outfit_references': [], 'tracks': []})
        groups[identifier]['before_group'] = ANCHOR
    pending, changes, evidence = {identifier: [] for identifier in PERMANENT_IDS}, [], []
    for group in result['groups']:
        retained = []
        for entry in group.get('tracks', []):
            track = by_file.get(entry['file'], {})
            content = by_content.get(track.get('id'), {})
            routes = [by_route[r] for r in content.get('route_ids', []) if r in by_route]
            target, reasons = mode_candidates(entry, group['id'], content, routes)
            old_name = entry['name']
            if target == 'mode-巅峰秀场' and entry['name'].startswith('尖兵陷阵 · '):
                entry['name'] = '巅峰秀场 · '+entry['name'].removeprefix('尖兵陷阵 · ')
            evidence.append({'file': entry['file'], 'name': entry['name'], 'original_group': group['id'],
                             'target_group': target or group['id'], 'candidate_groups': reasons})
            if target and target != group['id']:
                pending[target].append(entry)
                changes.append({'file': entry['file'], 'old_name': old_name, 'name': entry['name'], 'from': group['id'], 'to': target, 'basis': reasons[target]})
            else:
                retained.append(entry)
        group['tracks'] = retained
    for identifier in PERMANENT_IDS:
        groups[identifier]['tracks'].extend(pending[identifier])
    # The file is easy to edit: put the anchored block immediately above the old
    # catch-all. Runtime ordering uses before_group, so dates remain unchanged.
    original = [group for group in result['groups'] if group['id'] not in PERMANENT_IDS]
    block = [groups[identifier] for identifier in PERMANENT_IDS if groups[identifier]['tracks'] or groups[identifier].get('outfit_references')]
    index = next((i for i, group in enumerate(original) if group['id'] == ANCHOR), len(original))
    result['groups'] = original[:index]+block+original[index:]
    return result, {'schema_version': 1, 'moves': changes, 'evidence': evidence,
                    'permanent_order': [g['id'] for g in block],
                    'policy': 'Specific permanent gameplay groups appear before permanent-combat; existing metadata/dates and user names are preserved.'}


def main():
    import argparse
    import hashlib
    import json
    from pathlib import Path
    from pipeline_paths import REPOSITORY, GAME, protect_output
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, default=REPOSITORY/'public/data/story-melodies.json')
    parser.add_argument('--report', type=Path, default=REPOSITORY/'.build/permanent-preview/classification.json')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    protect_output(args.mapping, GAME); protect_output(args.report, GAME)
    read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
    original = args.mapping.read_bytes()
    mapping, report = reorganize(read(args.mapping), read(REPOSITORY/'public/data/library.json'),
                                 read(REPOSITORY/'references/analysis/content_groups.json'),
                                 read(REPOSITORY/'references/analysis/catalog.json'))
    report['source_mapping_sha256'] = hashlib.sha256(original).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    preview = REPOSITORY/'.build/permanent-preview/story-melodies.json'
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    if args.apply:
        if args.mapping.read_bytes() != original:
            raise SystemExit('Mapping changed concurrently; no changes applied.')
        backup = REPOSITORY/'.build/permanent-preview/backups'/report['source_mapping_sha256'][:16]
        backup.mkdir(parents=True, exist_ok=True); (backup/'story-melodies.json').write_bytes(original)
        temporary = args.mapping.with_suffix('.tmp')
        temporary.write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf8'); temporary.replace(args.mapping)
    print(f'Moved {len(report["moves"])} tracks; applied: {args.apply}; report: {args.report}')


if __name__ == '__main__':
    main()
