"""Localize music states and build dated, evidence-backed web library groups.

Original catalog names and audio paths remain intact. Only project JSON is written.
"""
import collections
import json
import re
from analyze import ROOT, TABLE, SYSTEM, LEVEL, COMBAT, BOSS, get, load, save, tr
WEB_DATA = '.local/extracted-public/data' if (ROOT/'.local/extracted-public').exists() else 'public/data'


def normalized(value):
    return re.sub(r'[\s·・!！~～，,。]', '', value or '').lower()


GROUPS = {}
for raw in TABLE['ActivityGroup'].values():
    row = tr(raw)
    chapter = next((tr(c) for c in TABLE['ActivityStoryChapter'].values() if c['ChapterId'] == row['Id']), {})
    match = re.search('「([^」]+)」', row.get('DesText', ''))
    name = chapter.get('Title') or (match[1] if match else '缭乱碎晶球' if row['CtrlName'] == 'ActivityBreakOutCtrl' else '')
    if name:
        GROUPS[row['Id']] = {'id': f"activity-{row['Id']}", 'name': name, 'date': row.get('StartTime', ''), 'basis': 'ActivityGroup.StartTime + ActivityStoryChapter.Title / ActivityGroup.DesText'}

ACTIVITY_ALIASES = {
    'dongxiang': ('冬香', 10101), 'dongxiangdig': ('冬香', 10101),
    'feilai': ('翡冷翠', 10103), 'fengying': ('风影', 10105), 'fengying2': ('风影', 10105),
    'duona': ('多娜', 10106), 'duonadig': ('多娜', 10106), 'yiye': ('乙叶', 20102),
    'huochui': ('火垂', 10107), 'sipai': ('斯帕克拉', 10108), 'maoyan': ('猫眼', 10109),
    'ailinuo': ('埃莉诺', 10111), 'ailei': ('艾蕾', 10112), 'chensha': ('尘沙', 20104), 'youye': ('优叶', 10113),
    'springfest': ('春节', 10104), 'christmas': ('圣诞', 20101),
    'summer25': ('夏日活动', 10100), 'summer25dig': ('夏日活动', 10100),
    'summer26': ('盛夏活动', 20103), 'summer262': ('盛夏探险', 10110),
}
TOKENS = {k.lower(): v for mapping in [SYSTEM, LEVEL, COMBAT, BOSS] for k, v in mapping.items()}
TOKENS.update({
    'prologue': '开篇', 'prologuel': '开篇', 'prologue_climb': '开篇·攀登',
    'prologue_firstcombat': '开篇·第一场战斗', 'prologue_secondcombat': '开篇·第二场战斗',
    'prologue_combatend': '开篇·战斗结束', 'prologue_skip': '开篇·跳过',
    'zizou': '尖兵陷阵', 'zizoupre': '尖兵陷阵·准备', 'zizousub': '尖兵陷阵·副段',
    'zizouvictory': '尖兵陷阵·胜利曲', 'zombie': '灾变防线', 'vampire': '灾变防线',
    'zombieforest': '灾变防线·森林', 'zombieruins': '灾变防线·遗迹', 'city': '城镇',
    'huochui': '火垂', 'yiye': '乙叶', 'fengying': '风影', 'fengying2': '风影·变体2',
    'chensha': '尘沙', 'dongxiang': '冬香', 'dongxiangdig': '冬香·探索',
    'feilai': '翡冷翠', 'sipai': '斯帕克拉', 'ailinuo': '埃莉诺', 'ailei': '艾蕾', 'youye': '优叶',
    'fengniao': get('MonsterManual', 1551056)['Name'],
    'fengniao2': get('MonsterManual', 1551056)['Name'] + '·变体2',
    'shasha': get('MonsterManual', 5050166)['Name'], 'gelei': get('MonsterManual', 3110100)['Name'],
    'nianshou': '年兽', 'medusa': '终焉绝响·首领配乐', 'medusa2': '终焉绝响·首领配乐·变体2',
    'cookie_start': '开始', 'cookie_end': '结束', 'cookie_free': '自由演奏',
    'cookietrans': '甜心梦工坊·过场', 'none': '默认', 'regular': '常规',
    'login': '登录', 'activity': '活动界面', 'camp': '营地', 'mainline': '主线',
    'questking': '任务玩法（名称待考）', 'shop_purchased': '采购完成', 'victory': '挑战成功', 'defeat': '挑战失败',
    'r': '旅人招募·R', 'sr': '旅人招募·SR', 'ssr': '旅人招募·SSR', 'diskr': '秘纹招募·R',
    'icecream1': '沁凉补给站', 'marble': '缭乱碎晶球',
})
for bpm in [40, 50, 60, 65, 68, 75]:
    TOKENS[f'cookie_bpm{bpm}'] = f'每分钟{bpm}拍'


def activity_from_id(activity_id):
    row = get('Activity', activity_id)
    return GROUPS.get(row.get('MidGroupId'))


FLOOR_ACTIVITIES = collections.defaultdict(set)
for level in TABLE['ActivityLevelsLevel'].values():
    group = activity_from_id(level.get('ActivityId'))
    if group:
        for floor in level.get('FloorId', []):
            FLOOR_ACTIVITIES[floor].add(group['id'])


def first_group(groups):
    return min(groups, key=lambda g: (g['date'] or '9999', g['id'])) if groups else None


def named_group(name):
    return first_group([g for g in GROUPS.values() if normalized(g['name']) == normalized(name)])


def gameplay(name, table, ids=None, date=''):
    dates = [r.get('StartTime') or r.get('OpenTime') for r in TABLE.get(table, {}).values()
             if (ids is None or r['Id'] in ids) and (r.get('StartTime') or r.get('OpenTime'))]
    return {'id': 'mode-' + name, 'name': name, 'date': min(dates) if dates else date, 'basis': table + ' earliest configured start'}


def resolve_group(track, category):
    states = {s['group'].lower(): s['value'].lower() for s in track['gamesyncs']}
    detail = track['details']
    if category == 'story':
        first = detail.get('first_appearance_candidate') or {}
        if first.get('table') == 'ActivityStory':
            row = get('ActivityStory', first.get('id'))
            group = GROUPS.get(row.get('ChapterId')) or named_group(first.get('story_set'))
            if group:
                return {**(named_group(group['name']) or group), 'basis': 'first_appearance_candidate -> ActivityStory.ChapterId -> ' + group['basis']}
        if first.get('table') == 'Story':
            row = get('Story', first.get('id')); chapter = get('StoryChapter', row.get('Chapter'))
            group = named_group(chapter.get('Desc'))
            if group:
                return {**group, 'basis': 'first_appearance_candidate -> StoryChapter.Desc -> ' + group['basis']}
        group = named_group(first.get('story_set'))
        if group:
            return group
        if first.get('table') == 'DiscIP':
            outfit = OUTFITS.get(first['id'])
            if outfit and outfit['activity']['id']:
                a = outfit['activity']; known = named_group(a['name'])
                if known:
                    return {**known, 'basis': 'first_appearance_candidate -> DiscIP -> outfit activity -> ActivityGroup'}
                return {'id': f"outfit-activity-{a['id']}", 'name': a['name'], 'date': a['date'], 'basis': 'first_appearance_candidate -> DiscIP -> outfit activity'}
        if first:
            if first.get('collection') == '旅人逸闻':
                character = re.split(r'[·・]', first.get('story_set', ''))[0]
                alias = next((v for v in ACTIVITY_ALIASES.values() if v[0] == character), None)
                if alias:
                    return {**GROUPS[alias[1]], 'basis': 'first_appearance_candidate -> traveler story character -> character activity alias'}
            name = ' · '.join(dict.fromkeys(v for v in [first.get('collection'), first.get('story_set')] if v))
            return {'id': 'story-' + name, 'name': name, 'date': first.get('open_time') or '', 'basis': 'first_appearance_candidate (candidate; not verified absolute premiere)'}
        return {'id': 'story-undated', 'name': '剧情音乐 · 首次出现待考', 'date': '', 'basis': 'no confirmed appearance'}

    token = states.get('system') or states.get('level') or ''
    if 'prologue' in states or token == 'prologuel':
        return {'id': 'prologue', 'name': '开篇', 'date': '', 'basis': 'user terminology + local Wwise Prologue state'}
    if token in ACTIVITY_ALIASES:
        return {**GROUPS[ACTIVITY_ALIASES[token][1]], 'basis': 'character/event state alias -> ' + GROUPS[ACTIVITY_ALIASES[token][1]]['basis']}
    # UI bundle names are direct evidence; generic shared maps are not assigned
    # to arbitrary later activities merely because their music is reused there.
    ui_groups = []
    for usage in track.get('unity_state_usages', []):
        match = re.search(r'ui_activity_(\d+)\.unity3d', usage.get('bundle', ''))
        if match and int(match[1]) in GROUPS:
            ui_groups.append(GROUPS[int(match[1])])
    group = first_group(ui_groups)
    if group and states.get('system'):
        return {**group, 'basis': 'local Unity state component -> ui_activity bundle -> ' + group['basis']}
    if token.startswith('zizou'):
        return gameplay('尖兵陷阵', 'Activity', [900001])
    if token.startswith('zombie') or token == 'vampire':
        return gameplay('灾变防线', 'VampireRankSeason')
    if token.startswith('mainline'):
        number = re.search(r'\d+', token)
        if number:
            chapter = next((tr(c) for c in TABLE['StoryChapter'].values() if c.get('Index') == number[0].zfill(2)), {})
            group = named_group(chapter.get('Desc'))
            if group:
                return group
            return {'id': 'mainline-' + number[0], 'name': '主线 · ' + chapter.get('Desc', chapter.get('Name', '第' + number[0] + '章')), 'date': chapter.get('OpenTime', ''), 'basis': 'StoryChapter'}
    if token.startswith(('cookie', 'goldDigger'.lower(), 'gift')) or token in ['sudu', 'suduin', 'icecream1', 'marble', 'chess', 'card', 'cardin', 'date']:
        names = {'cookie': '甜心梦工坊', 'golddigger': '幸运寻宝铲', 'gift': '豪礼抛物线', 'sudu': '速度与机擎',
                 'suduin': '速度与机擎', 'icecream1': '沁凉补给站', 'marble': '缭乱碎晶球', 'chess': '缭乱碎晶球', 'card': '命运星牌局', 'cardin': '命运星牌局', 'date': '闻香识魔女'}
        key = next((k for k in names if token.startswith(k)), token); name = names[key]
        matches = [r for r in tr(TABLE['Activity']).values() if name in r.get('Name', '')]
        if name == '甜心梦工坊':
            matches = [r for r in TABLE['Activity'].values() if r.get('ActivityType') == 4]
        if token in ['card', 'cardin']:
            matches = [r for r in TABLE['Activity'].values() if r.get('ActivityType') == 18]
        date = min((r['StartTime'] for r in matches if r.get('StartTime')), default='')
        return {'id': 'mode-' + name, 'name': name, 'date': date, 'basis': 'Wwise state + earliest matching Activity configuration'}
    if states.get('bosstype', '').startswith('medusa') or token in ['bossrush', 'groupcombat', 'lieying']:
        name = '终焉绝响' if token != 'groupcombat' and token != 'lieying' else '猎影合围'
        return gameplay(name, 'Activity', [510001] if name == '终焉绝响' else [])
    boss = states.get('bosstype', '')
    if boss:
        candidates = []
        for usage in track.get('config_usages', []):
            if usage['table'] == 'ActivityLevelsFloor' and usage.get('match') == 'all_recipe_fields':
                candidates.extend(g for g in GROUPS.values() if g['id'] in FLOOR_ACTIVITIES[usage['id']])
        if candidates:
            return {**first_group(candidates), 'basis': 'matched Wwise recipe -> ActivityLevelsFloor -> ActivityLevelsLevel.ActivityId -> Activity.MidGroupId'}
    return {'id': 'permanent-' + category, 'name': '常驻玩法' if category == 'combat' else '常驻系统', 'date': '', 'basis': 'no unique dated activity evidence'}


def localize(track, category):
    states = {s['group'].lower(): s['value'] for s in track['gamesyncs']}
    if category == 'story':
        first = track['details'].get('first_appearance_candidate') or {}
        raw = track['details'].get('music_state', '')
        number = re.search(r'\d+', raw)
        parts = ['剧情配乐' + (' ' + number[0] if number else '')]
        parts.extend(v for v in [first.get('story_set'), first.get('chapter_name')] if v)
        return ' · '.join(dict.fromkeys(parts)) if first else parts[0] + ' · 首次出现待考'
    parts = []
    for group in ['system', 'level', 'bosstype', 'combat', 'prologue', 'cookie', 'recruit_rarity', 'loading']:
        value = states.get(group)
        if not value:
            continue
        key = value.lower()
        if key in ACTIVITY_ALIASES and group in ['system', 'level']:
            label = GROUPS[ACTIVITY_ALIASES[key][1]]['name']
            if key.endswith('dig'):
                label += '·探索'
            if key == 'fengying2':
                label += '·变体2'
        else:
            label = TOKENS.get(key)
        if label is None:
            UNRESOLVED.add((group, value)); label = value
        parts.append(label)
    if 'loading' in states:
        parts.insert(0, '加载画面')
    return ' · '.join(dict.fromkeys(parts)) or track['title']


def main():
    global OUTFITS, UNRESOLVED
    OUTFITS = {o['id']: o for o in load(WEB_DATA+'/outfits.json')['items']}
    UNRESOLVED = set(); audit = []; by_content = collections.defaultdict(list)
    raw_tracks = load('data/catalog.json')['tracks']
    by_id = {t['id']: t for t in raw_tracks}
    for source in raw_tracks:
        if source.get('pcm_sha256') and source['category'] == 'outfit':
            by_content[source['pcm_sha256']].append({'source': source, 'category': 'outfit', 'title': source['title']})
    for category in ['combat', 'story', 'system']:
        for source in load(f'data/categories/{category}.json')['tracks']:
            if not source.get('audio_path') or not source.get('audio'):
                continue
            title = localize(source, category); group = resolve_group(source, category)
            audit.append({'id': source['id'], 'category': category, 'source_title': source['title'], 'title': title,
                          'activity': group, 'source_states': source['gamesyncs'], 'first_appearance_candidate': source['details'].get('first_appearance_candidate')})
            suppressed = any(s['group'].lower() == 'system' and s['value'].lower() == 'questking' for s in source['gamesyncs'])
            by_content[source['pcm_sha256']].append({'source': source, 'category': category, 'title': title, 'group': group, 'suppressed_reference': suppressed})

    registry = []; manifests = {c: [] for c in ['combat', 'story', 'system']}
    # A single PCM fingerprint has exactly one primary location across the site.
    # Outfit music belongs to its existing archive; shared interface themes use
    # system, then gameplay, then story. Every other use stays linked as context.
    priority = {'outfit': 0, 'system': 1, 'combat': 2, 'story': 3}
    for pcm, rows in by_content.items():
        display_rows = [r for r in rows if not r.get('suppressed_reference')]
        if not display_rows:
            raise ValueError('Suppressed music has no retained activity reference: ' + pcm)
        owner = min(display_rows, key=lambda r: (priority[r['category']],
                    r.get('group', {}).get('date') or '9999', r['source']['id']))
        category = owner['category']; source = owner['source']
        identifier = 'audio-' + pcm
        category_rows = [r for r in display_rows if r['category'] == category]
        common_parts = [p for p in re.split(r'\s*·\s*', owner['title']) if all(p in r['title'] for r in category_rows)]
        title = ' · '.join(common_parts) or owner['title']
        uses = list(dict.fromkeys(r['title'] for r in display_rows))
        activities = list({r['group']['id']: r['group'] for r in display_rows if 'group' in r}.values())
        entry = {'id': identifier, 'pcm_sha256': pcm, 'title': title, 'category': category,
                 'path': '/' + source['audio_path'], **source['audio'],
                 'uses': uses, 'activities': activities, 'categories': sorted(set(r['category'] for r in rows)),
                 'route_ids': [r['source']['id'] for r in rows],
                 'aliases': list(dict.fromkeys(r['source']['title'] for r in rows)),
                 'source_states': [s for r in rows for s in r['source']['gamesyncs']],
                 'alternate_playback': list({json.dumps(r['source']['audio'], sort_keys=True): r['source']['audio'] for r in rows}.values())}
        if category == 'outfit':
            entry['outfit_id'] = source['details']['disc_id']
        else:
            group = owner['group']
            # Use the first known context within the owner category; no copies
            # are inserted in later activities or other category manifests.
            entry.update({'group_id': group['id'], 'activity': group,
                          'source_title': ' / '.join(entry['aliases'])})
            manifests[category].append(entry)
        registry.append(entry)

    content_index = {e['pcm_sha256']: e for e in registry}
    for outfit in OUTFITS.values():
        for music in outfit['music']:
            source_id = music.get('source_route_id', music['id'])
            source = by_id[source_id]; entry = content_index[source['pcm_sha256']]
            music.update({'source_route_id': source_id, 'id': entry['id'], 'content_id': entry['id'],
                          'shared_uses': list(dict.fromkeys(r['title'] for r in by_content[entry['pcm_sha256']] if r['category'] != 'outfit' and not r.get('suppressed_reference')))})
    outfit_manifest = load(WEB_DATA+'/outfits.json'); outfit_manifest['items'] = list(OUTFITS.values())
    save(WEB_DATA+'/outfits.json', outfit_manifest)
    save('data/content_groups.json', {'schema_version': 1, 'identity': 'decoded PCM SHA-256',
         'ownership_policy': 'one primary location: outfit > system > combat > story; other uses and alternative loop metadata retained',
         'contents': registry})
    for category, tracks in manifests.items():
        groups = {}
        for row in tracks:
            group = row['activity']
            groups.setdefault(group['id'], {**group, 'track_ids': []})['track_ids'].append(row['id'])
        ordered = sorted(groups.values(), key=lambda g: (g['date'], g['name']), reverse=True)
        order = {g['id']: i for i, g in enumerate(ordered)}
        tracks.sort(key=lambda t: (order[t['group_id']], t['title'], t['id']))
        save(f'{WEB_DATA}/{category}.json', {'schema_version': 2, 'groups': ordered, 'tracks': tracks})
        print(category, len(tracks), 'unique songs;', len(ordered), 'groups')
    combined = [entry for entry in registry if entry['category'] != 'outfit' and entry['duration_seconds'] >= 60]
    combined_groups = {}
    for entry in combined:
        group = entry['activity']
        combined_groups.setdefault(group['id'], {**group, 'track_ids': [], 'outfit_references': []})['track_ids'].append(entry['id'])
    for outfit in OUTFITS.values():
        release = outfit['activity']
        group = GROUPS.get(release['id']) or activity_from_id(release['id'])
        if not group or not release['date'] or release['date'][:10] != group['date'][:10]:
            continue
        target = combined_groups.setdefault(group['id'], {**group, 'track_ids': [], 'outfit_references': []})
        target['outfit_references'].append({'outfit_id': outfit['id'], 'name': outfit['name'],
            'cover': outfit['thumbnail'], 'content_ids': [m['id'] for m in outfit['music']],
            'basis': 'first known outfit release in this activity; not shared-music reuse'})
    ordered = sorted(combined_groups.values(), key=lambda g: (g['date'], g['name']), reverse=True)
    order = {g['id']: i for i, g in enumerate(ordered)}
    combined.sort(key=lambda t: (order[t['group_id']], t['title'], t['id']))
    save(WEB_DATA+'/library.json', {'schema_version': 2, 'groups': ordered, 'tracks': combined})
    print('combined', len(combined), 'unique songs;', len(ordered), 'groups')
    save('data/library_catalog.json', {'schema_version': 1, 'tracks': audit,
         'date_policy': 'Activities use configured start times; shared songs use first known matching activity. Story attribution retains the existing first appearance candidate boundary. Undated permanent content sorts last.',
         'unresolved_states': sorted(UNRESOLVED)})
    save('data/music_localization.json', {'tokens': TOKENS,
         'activity_aliases': {k: {'character_or_event': v[0], 'activity_id': v[1], 'activity': GROUPS[v[1]]} for k, v in ACTIVITY_ALIASES.items()},
         'evidence': ['user-confirmed character and mode names', 'local Wwise state components and activity bundle names', 'ActivityLevelsLevel -> Activity -> ActivityGroup', 'MonsterSkin -> MonsterManual'],
         'uncertain': {'questKing': 'No direct UI/configuration usage located; display 任务玩法（名称待考）', 'medusa': 'Used by JointDrillFloor; display mode name rather than guessing a boss from the English codename'}})
    if UNRESOLVED:
        print('Raw state names retained:', repr(sorted(UNRESOLVED)), flush=True)


if __name__ == '__main__':
    main()
