"""Create a small web manifest, native card layouts, optimized artwork and UI font."""
from pathlib import Path
import concurrent.futures
import json
import math
import re
import sys
import collections
import UnityPy
from PIL import Image
from analyze import ROOT, TABLE, get, load, tr, save

from pipeline_paths import GAME
INSTALL = GAME / 'xtlr_Data/StreamingAssets/InstallResource'
VERSION = GAME / 'Persistent_Store/AssetBundles'
WEB_ROOT = ROOT/'.local/extracted-public' if (ROOT/'.local/extracted-public').exists() else ROOT/'public'


def activity_order():
    candidates = collections.defaultdict(list)
    groups = list(TABLE.get('ActivityGroup', {}).values())
    chapters = list(TABLE.get('ActivityStoryChapter', {}).values())

    def label(group):
        chapter = next((r for r in chapters if r.get('ChapterId') == group.get('Id')), None)
        if chapter:
            return tr(chapter.get('Title'))
        desc = tr(group.get('DesText', ''))
        match = re.search('「([^」]+)」', desc)
        return match[1] if match else '限时活动'

    for group in groups:
        if not group.get('StartTime'):
            continue
        for item in group.get('RewardsShow', []):
            candidates[item].append({'date': group['StartTime'], 'name': label(group),
                                     'id': group['Id'], 'basis': 'ActivityGroup.RewardsShow'})
    packages = collections.defaultdict(set)
    for row in TABLE.get('GachaPkg', {}).values():
        packages[row['PkgId']].add(row['GoodsId'])
    for gacha in TABLE.get('Gacha', {}).values():
        if not gacha.get('StartTime') or not gacha.get('ATypeUpPkg'):
            continue
        group = next((r for r in groups if r.get('StartTime') == gacha['StartTime']
                      and r.get('ActivityGroupType') in [1, 2]), None)
        for item in packages[gacha['ATypeUpPkg']]:
            candidates[item].append({'date': gacha['StartTime'],
                                     'name': label(group) if group else tr(gacha['Name']),
                                     'id': group['Id'] if group else gacha['Id'],
                                     'basis': 'Gacha.ATypeUpPkg -> GachaPkg.GoodsId (first known banner)'})
    for reward in TABLE.get('LoginRewardGroup', {}).values():
        activity = TABLE.get('Activity', {}).get(str(reward.get('RewardGroupId')), {})
        if activity.get('StartTime'):
            for field in ['RewardId1', 'RewardId2']:
                if reward.get(field):
                    candidates[reward[field]].append({'date': activity['StartTime'], 'name': tr(activity.get('Name')),
                                                     'id': activity['Id'], 'basis': 'LoginRewardGroup -> Activity'})
    out = {}
    for item, entries in candidates.items():
        out[item] = min(entries, key=lambda e: e['date'])
    save('data/outfit_activity_order.json', {'items': out, 'fallback': '常驻与早期秘纹；没有可核实活动日期的条目置于最后，不以秘纹编号冒充时间'})
    return out


def optimize(source, target, size=1400):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return
    image = Image.open(source).convert('RGBA')
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    image.save(target, 'WEBP', quality=91, method=4)


from disc_layout import layout


def skill(table, group):
    candidates = [v for v in TABLE.get(table, {}).values() if v.get('GroupId') == group]
    if not candidates:
        return None
    row = tr(min(candidates, key=lambda v: v.get('Level', 1)))
    desc = row.get('Desc', '')
    desc = re.sub(r'\{(\d+)\}', lambda m: str(row.get('Param' + m[1], m[0])), desc)
    desc = desc.replace('\\x0b', '\n').replace('\x0b', '\n')
    desc = re.sub(r'##(.*?)#\d+#', r'\1', desc)
    row['formatted_description'] = desc
    return row


def prepare(item):
    code = item['code']
    art = item['artwork']
    images = {i['name']: i for i in art['images']}
    cover = next((i for i in art['images'] if i['role'] == 'cover'), art['images'][0])
    optimize(ROOT / cover['path'], WEB_ROOT / f'art/{code}/cover.webp')
    optimize(ROOT / cover['path'], WEB_ROOT / f'art/{code}/thumb.webp', 280)
    native_sprites = {}
    card = layout(item, sprite_exports=native_sprites)
    for layer in card['layers']:
        source = images.get(layer['name'])
        if source:
            optimize(ROOT / source['path'], WEB_ROOT / layer['path'].lstrip('/'))
        else:
            target = WEB_ROOT / layer['path'].lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            native_sprites[layer['name']].read().image.save(target, 'WEBP', lossless=True, method=4, exact=True)
    disc = item['disc_config']
    item_config = get('Item', item['id'])
    candidates = [t for t in TRACKS if t['details'].get('disc_id') == item['id']]
    base_rows = [r for r in TABLE.get('Attribute', {}).values() if r.get('GroupId') == disc.get('AttrBaseGroupId')]
    base = min(base_rows, key=lambda r: r.get('lvl', 1)) if base_rows else {}
    attr_names = {'Atk': '基础攻击', 'Hp': '生命', 'Def': '防御', 'NORMALDMG': '普攻伤害',
                  'SKILLDMG': '技能伤害', 'ULTRADMG': '终结技伤害', 'WEE': '水系伤害',
                  'FEE': '火系伤害', 'SEE': '风系伤害', 'AEE': '地系伤害', 'LEE': '光系伤害',
                  'DEE': '暗系伤害', 'CritRate': '暴击率', 'CritPower': '暴击伤害'}
    attributes = [{'name': name, 'value': str(base[key]) if key in ['Atk', 'Hp', 'Def'] else f'{base[key] / 100:g}%'}
                  for key, name in attr_names.items() if base.get(key)]
    music = []
    for kind in ['核心旋律', '凯旋旋律']:
        group = [t for t in candidates if t['details']['variant'] == kind]
        if not group:
            continue
        t = sorted(group, key=lambda t: (t['source'] != 'version', t['source'] != 'regenerated_version'))[0]
        music.append({'id': t['id'], 'title': kind, 'path': '/' + t['audio_path'], **t['audio']})
    return {
        'id': item['id'], 'code': code, 'name': item['name'],
        'storyTitle': item['story_title'], 'story': item['story_text'],
        'literary': item['literary'], 'description': item['description'],
        'characters': item['characters'], 'element': disc.get('EET', 7),
        'rarity': {1: 5, 2: 4, 3: 3}.get(item_config.get('Rarity'), 3),
        'tags': [get('DiscTag', v).get('Title') for v in disc.get('Tags', [])],
        'attributes': attributes,
        'cover': f'/art/{code}/cover.webp', 'thumbnail': f'/art/{code}/thumb.webp',
        'staticImage': '/' + cover['path'].replace('\\', '/'),
        'card': card, 'music': music,
        'mainSkill': skill('MainSkill', disc.get('MainSkillGroupId')),
        'secondarySkills': [s for s in [skill('SecondarySkill', disc.get('SecondarySkillGroupId1')),
                                      skill('SecondarySkill', disc.get('SecondarySkillGroupId2'))] if s],
        'avgScript': item['music_config'].get('AvgId'),
        'activity': ACTIVITY.get(item['id'], {'date': '', 'name': '常驻与早期秘纹', 'id': 0, 'basis': 'unresolved_activity_date'}),
    }


TRACKS = load('data/catalog.json')['tracks']
ACTIVITY = activity_order()


def main():
    items = load('data/categories/outfit_items.json')['items']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = []
        for i, r in enumerate(pool.map(prepare, items), 1):
            results.append(r)
            if i % 20 == 0:
                print(i, '/', len(items), flush=True)
    results.sort(key=lambda x: (x['activity']['date'], x['activity']['id'], int(x['code'])), reverse=True)
    save(str(WEB_ROOT.relative_to(ROOT) / 'data/outfits.json'), {'schemaVersion': 1, 'items': results})
    # Keep the game's own UI font. A subset is generated separately when fonttools is available.
    out = ROOT / 'assets/fonts'
    out.mkdir(parents=True, exist_ok=True)
    p = VERSION / 'font.unity3d'
    env = UnityPy.load(str(p if p.exists() else INSTALL / 'font.unity3d'))
    for o in env.objects:
        if o.type.name == 'Font':
            font = o.read()
            if font.m_Name in ['MiSans-Semibold', 'MiSans-Bold']:
                (out / (font.m_Name + '.ttf')).write_bytes(bytes(font.m_FontData))
    print('ready', len(results), sum(len(r['card']['layers']) for r in results), 'native layers', flush=True)


if __name__ == '__main__':
    main()
