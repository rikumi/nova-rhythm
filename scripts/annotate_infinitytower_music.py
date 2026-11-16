"""Annotate Infinity Tower menu and random combat arrangements from frozen recipes."""
import argparse
import hashlib
import json
from pathlib import Path
from pipeline_paths import REPOSITORY, GAME, protect_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    read = lambda name: json.loads((REPOSITORY/name).read_text(encoding='utf-8-sig'))
    mapping_path = REPOSITORY/'public/data/story-melodies.json'
    protect_output(mapping_path, GAME)
    original = mapping_path.read_bytes()
    mapping = json.loads(original.decode('utf-8-sig'))
    by_file = {t['path']: t for t in read('public/data/library.json')['tracks']}
    contents = {c['id']: c for c in read('references/analysis/content_groups.json')['contents']}
    routes = {r['id']: r for r in read('references/analysis/catalog.json')['tracks']}
    evidence = []
    for group in mapping['groups']:
        if group['id'] != 'mode-心危擂台':
            continue
        for entry in group['tracks']:
            content = contents.get(by_file.get(entry['file'], {}).get('id'), {})
            sources = [routes[r] for r in content.get('route_ids', []) if r in routes]
            states = content.get('source_states', [])
            system = any(s['group'] == 'system' and s['value'].lower() == 'endlesstower' for s in states)
            normal = any(s['group'] == 'combat' and s['value'] == 'combatNomal' for s in states)
            if system:
                description = '塔、难度及关卡选择界面。'
                choices = None
            elif normal:
                choices = next((r['random_choices'] for r in sources if r.get('random_choices')), None)
                if not choices or len(choices) != 4 or any(c not in [1, 2] for c in choices):
                    raise ValueError('Expected four binary random selectors: '+entry['file'])
                variants = ' / '.join('A' if c == 1 else 'B' for c in choices)
                description = f'普通关卡战斗；随机段落组合 {variants}（循环第 1、2、4、5 段）。'
            else:
                continue
            entry['description'] = description
            evidence.append({'file': entry['file'], 'name': entry['name'], 'description': description,
                             'random_choices': choices, 'route_ids': [r['id'] for r in sources],
                             'states': states, 'config_usages': sources[0].get('config_usages', []),
                             'unity_state_usages': sources[0].get('unity_state_usages', [])})
    report = {'schema_version': 1,
              'basis': 'Menu: ui_infinitytower towerList/diffListView/lvList system state; combat: InfinityTowerMap BGM and TXTP random group selectors.',
              'random_selection': {'source': 'references/txtp/install/install-082d09f35a2d.txtp',
                  'intro_seconds': 1.71428571428574,
                  'loop_sections': [{'section': 1, 'selector': 1, 'A': '623406877.wem 42.857143–70.285714s', 'B': '623406877.wem 1.714286–29.142857s'},
                                    {'section': 2, 'selector': 2, 'A': '623406877.wem 29.142857–42.857143s', 'B': '147622662.wem'},
                                    {'section': 3, 'selector': None, 'fixed': '840557293.wem'},
                                    {'section': 4, 'selector': 3, 'A': ['690354636.wem', '762396951.wem'], 'B': ['573861789.wem', '177005291.wem']},
                                    {'section': 5, 'selector': 4, 'A': '623406877.wem 29.142857–42.857143s', 'B': '147622662.wem'}],
                  'note': 'A/B denotes frozen export choices, not named gameplay states, floors or difficulties. The third loop section and intro are fixed; four independent binary selectors produce sixteen combinations.'},
              'entries': evidence}
    work = REPOSITORY/'.build/infinitytower-annotations'
    work.mkdir(parents=True, exist_ok=True)
    (work/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    (work/'story-melodies.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    if args.apply:
        if mapping_path.read_bytes() != original:
            raise SystemExit('Mapping changed concurrently; no changes applied.')
        (work/('backup-'+hashlib.sha256(original).hexdigest()[:16]+'.json')).write_bytes(original)
        temporary = mapping_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        try:
            temporary.replace(mapping_path)
        except PermissionError:
            # Some Windows editors allow writing but keep a handle without delete sharing.
            if mapping_path.read_bytes() != original:
                raise SystemExit('Mapping changed concurrently; no changes applied.')
            mapping_path.write_bytes(temporary.read_bytes())
            temporary.unlink()
        (REPOSITORY/'references/infinitytower-music-usages.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(f'Annotated: {len(evidence)}; applied: {args.apply}')


if __name__ == '__main__':
    main()
