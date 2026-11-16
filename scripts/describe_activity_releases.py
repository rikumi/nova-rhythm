"""Preview activity descriptions from first known character banners and story type."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from pipeline_paths import REPOSITORY, GAME, protect_output


def describe(mapping, tables, language):
    packages = collections.defaultdict(set)
    characters = tables['Character']
    for row in tables['GachaPkg'].values():
        if str(row['GoodsId']) in characters:
            packages[row['PkgId']].add(row['GoodsId'])
    first = {}
    for row in tables['Gacha'].values():
        if not row.get('StartTime'):
            continue
        for character in packages[row.get('ATypeUpPkg')]:
            if character not in first or row['StartTime'] < first[character]['StartTime']:
                first[character] = row
    evidence = []
    for group in mapping['groups']:
        if not group['id'].startswith('activity-'):
            continue
        activity = tables['ActivityGroup'].get(group['id'].split('-', 1)[1])
        if not activity:
            continue
        introduced = [identifier for identifier, banner in first.items() if banner['StartTime'] == activity.get('StartTime')]
        names = [language['Character'][characters[str(identifier)]['Name']] for identifier in sorted(introduced)]
        text = language['ActivityGroup'].get(activity.get('DesText'), '')
        kind = '主线更新剧情' if '主线故事剧情' in text else '限时活动剧情'
        suggested = kind+'：'+' / '.join(names) if names else ''
        previous = group.get('description', '')
        if suggested and not previous.strip():
            group['description'] = suggested
        evidence.append({'group_id': group['id'], 'name': group['name'], 'date': activity.get('StartTime'),
                         'character_ids': introduced, 'characters': names,
                         'banner_ids': [first[identifier]['Id'] for identifier in introduced],
                         'story_type_evidence': text, 'suggested_description': suggested,
                         'description': group.get('description', ''), 'preserved_user_description': bool(previous.strip())})
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tables', type=Path, required=True, help='CN directory containing bin/ and language/zh_CN/')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    mapping_path = REPOSITORY/'public/data/story-melodies.json'
    protect_output(mapping_path, GAME)
    original = mapping_path.read_bytes()
    mapping = json.loads(original.decode('utf-8-sig'))
    read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
    names = ['Character', 'Gacha', 'GachaPkg', 'ActivityGroup']
    tables = {name: read(args.tables/'bin'/(name+'.json')) for name in names}
    language = {name: read(args.tables/'language/zh_CN'/(name+'.json')) for name in ['Character', 'ActivityGroup']}
    evidence = describe(mapping, tables, language)
    work = REPOSITORY/'.build/activity-descriptions'
    work.mkdir(parents=True, exist_ok=True)
    (work/'story-melodies.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    report = {'basis': 'First known Gacha.ATypeUpPkg -> GachaPkg.GoodsId character banner at ActivityGroup.StartTime; story type from ActivityGroup.DesText. Existing user descriptions take precedence.',
              'source_sha256': {name: hashlib.sha256((args.tables/'bin'/(name+'.json')).read_bytes()).hexdigest() for name in names}, 'entries': evidence}
    (work/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    if args.apply:
        if mapping_path.read_bytes() != original:
            raise SystemExit('Mapping changed concurrently; no changes applied.')
        (work/('backup-'+hashlib.sha256(original).hexdigest()[:16]+'.json')).write_bytes(original)
        temporary = mapping_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        temporary.replace(mapping_path)
        (REPOSITORY/'references/activity-character-releases.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(f'Activities: {len(evidence)}; filled: {sum(bool(e["suggested_description"]) and not e["preserved_user_description"] for e in evidence)}; applied: {args.apply}')


if __name__ == '__main__':
    main()
