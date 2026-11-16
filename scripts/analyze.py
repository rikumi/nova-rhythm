"""Build machine-readable catalog from local Wwise evidence and versioned data mirrors."""
from pathlib import Path
import collections
import hashlib
import json
import re

from pipeline_paths import ROOT
TABLES = ROOT / 'data/upstream/tables/CN'
LUA = ROOT / 'data/upstream/lua/Lua'


def load(path, default=None):
    p = ROOT / path
    return json.loads(p.read_text(encoding='utf8')) if p.exists() else default


def save(path, value):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def fnv(value):
    h = 2166136261
    for c in value.lower().encode('utf8'):
        h = ((h * 16777619) & 0xffffffff) ^ c
    return h


def safe(value):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value)).strip(' .')[:130]


LANG = {}
for p in (TABLES / 'language/zh_CN').glob('*.json'):
    LANG.update(json.loads(p.read_text(encoding='utf8')))
TABLE = {p.stem: json.loads(p.read_text(encoding='utf8')) for p in (TABLES / 'bin').glob('*.json')}


def tr(value):
    if isinstance(value, str):
        return LANG.get(value, value)
    if isinstance(value, list):
        return [tr(x) for x in value]
    if isinstance(value, dict):
        return {k: tr(v) for k, v in value.items()}
    return value


def get(table, key):
    return tr(TABLE.get(table, {}).get(str(key), {}))


SYSTEM = {
    'launch': '启动画面', 'main': '登录与主界面', 'recruit': '招募过程',
    'shop': '采购商店', 'victory2': '探索完成', 'formation': '编队',
    'levelSelect': '关卡选择', 'bossRank': '巅峰猎场', 'regionBoss': '区域首领',
    'bossRush': '终焉绝响', 'endlessTower': '无尽之塔', 'groupCombat': '猎影合围',
    'card': '命运星牌局', 'cardin': '命运星牌局-入场',
    'gift': '豪礼抛物线', 'giftin': '豪礼抛物线-序奏',
    'goldDigger1': '幸运寻宝铲', 'goldDigger1in': '幸运寻宝铲-入场',
    'sudu': '速度与机擎', 'suduin': '速度与机擎-大厅',
    'lieYing': '猎影合围', 'lieying': '猎影合围',
    'cookie': '甜心梦工坊', 'cookie2': '甜心梦工坊-变体2',
    'cookie3': '甜心梦工坊-变体3', 'cookie4': '甜心梦工坊-变体4',
    'icecream1': '冰淇淋玩法', 'duel': '尖兵陷阵', 'duelIn': '尖兵陷阵-入场',
    'chess': '缭乱碎晶球', 'date': '闻香识魔女',
    'houZhai': '后宅', 'creation': '共鸣创作', 'fastBattle': '快速战斗',
    'vampire': '幸存者玩法', 'marble': '弹珠玩法',
    'zizou': '自走棋', 'zizouPre': '自走棋-准备', 'zizouSub': '自走棋-副段',
    'mainline3': '主线第三章', 'mainline4': '主线第四章',
    'mainline4Dig': '主线第四章-探索', 'mainline5Dig': '主线第五章-探索',
    'mainline6': '主线第六章', 'duonaDig': '多娜活动-探索',
    'summer25': '欢歌劲浪·闪耀假日', 'summer25dig': '欢歌劲浪·闪耀假日-探索',
    'summer26': '盛夏活动2026', 'christmas': '闪耀的使者与圣夜的精灵',
    'youye': '幽夜活动',
}
LEVEL = {
    'forest': '森林', 'forestRuins': '森林遗迹', 'waterBridge': '水城',
    'Forest': '森林', 'WaterBridge': '水城', 'ForestRuins': '森林遗迹',
    'desert': '沙漠', 'desert2': '沙漠-变体2', 'desert3': '沙漠-变体3',
    'company': '公司', 'countryside': '乡野', 'darkForest': '暗林',
    'zombieForest': '侵蚀森林', 'zombieRuins': '侵蚀遗迹',
    'rogueLike': '星塔', 'rogueWater': '流水与暗影',
    'rogueFire': '烈焰与尘埃', 'rogueWind': '风暴与闪电',
    'endlessTower': '无尽之塔', 'bossFight': '首领战',
    'breakout': '突围玩法', 'towerDefense': '游棋保卫战',
    'towerDefence2': '游棋保卫战-变体2', 'travelerDuel': '尖兵陷阵',
    'trail': '旅人试炼', 'prologuel': '序章', 'Prologuel': '序章',
    'springFest': '春节活动', 'summer25': '欢歌劲浪·闪耀假日',
    'summer26': '盛夏活动2026', 'christmas': '闪耀的使者与圣夜的精灵',
    'fengying': '风影活动', 'duoNa': '多娜活动', 'yiYe': '一叶活动',
    'feilai': '飞来活动', 'huoChui2': '火垂-变体2', 'maoYan': '猫眼',
}
COMBAT = {'combatNomal': '普通战斗', 'combatBoss': '首领战斗',
          'combatElite': '精英战斗', 'combatLeader': '领袖战斗',
          'combatChallenge': '挑战战斗', 'combatRealChallenge': '高难挑战',
          'explore': '探索', 'shopIn': '进入交易之间', 'shopOut': '离开交易之间',
          'BossDefeat': '首领击败', 'victory': '挑战成功', 'victory2': '探索完成',
          'defeat': '探索失败'}
BOSS = {
    'chess': '赛尔西亚·疯狂战车', 'chess2': '赛尔西亚·绝望战车',
    'magician': '崇高傀儡·科佩里乌斯与奥林匹娅', 'magician2': '崇高傀儡-变体2',
    'shiLaimu': '冻冻王三世', 'shilaimu': '冻冻王三世', 'shiLaimu2': '冻冻王三世-变体2',
    'chuZi': '味觉惊惧', 'chuZi2': '味觉惊惧-变体2',
    'daGuanzi': '热嘟噜噗男爵', 'daGuanzi2': '热嘟噜噗男爵-变体2',
    'fan': '吹灰夫人', 'fan2': '吹灰夫人-变体2',
    'lamp': '终宵萤辉', 'lamp2': '终宵萤辉-变体2',
    'liRong': '禁断丽容', 'liRong2': '禁断丽容-变体2',
    'fengCao': '流风美人', 'fengCao2': '流风美人-变体2',
    'haiTu': '咕噜六角鲸', 'haiTu2': '咕噜六角鲸-变体2',
    'haSana': '哈萨娜', 'maoYan': '猫眼', 'huaYuan': '花原',
    'huoChui': '火垂', 'huoChui2': '火垂-变体2', 'huoChui3': '火垂-变体3',
    'wuyu': '雾语', 'penguin': '企鹅狩猎', 'nianShou2': '年兽-变体2',
    'tiaoWuJi_combat': '怪诞舞者-战斗', 'tiaoWuJi_ultimate': '怪诞舞者-终结技',
    'medusa': 'medusa', 'medusa2': 'medusa-变体2',
}


def literals(body):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?|true|false|nil', body)
    values = []
    for token in tokens:
        try:
            values.append(json.loads(token) if token != 'nil' else None)
        except json.JSONDecodeError:
            values.append(token.strip('"'))
    return values


def story_contexts():
    contexts = collections.defaultdict(list)
    for table in ['Story', 'ActivityStory', 'StorySetSection', 'ActivityAvgLevel']:
        for raw in TABLE.get(table, {}).values():
            row = tr(raw)
            script = row.get('AvgLuaName') or row.get('AVGId') or row.get('StoryId')
            if not script:
                continue
            if table == 'Story':
                chapter = get('StoryChapter', row.get('Chapter'))
                story_set = chapter.get('Name', '主线')
                collection = get('StoryLine', chapter.get('StoryLineId')).get('TitleMain', '主线故事')
            elif table == 'StorySetSection':
                chapter = get('StorySetChapter', row.get('ChapterId'))
                story_set = chapter.get('Name', '故事集')
                collection = get('StorySetTab', chapter.get('TabId')).get('TabName', '故事集')
            elif table == 'ActivityStory':
                chapter = get('ActivityStoryChapter', row.get('ChapterId'))
                if not chapter:
                    chapter = next((tr(v) for v in TABLE.get('ActivityStoryChapter', {}).values()
                                    if v.get('ChapterId') == row.get('ChapterId')), {})
                story_set = chapter.get('Title', '活动故事')
                collection = '活动故事'
            else:
                chapter = get('Activity', row.get('ActivityId'))
                story_set = chapter.get('Name', '活动故事')
                collection = '活动故事'
            contexts[script].append({
                'table': table, 'id': row['Id'], 'script_id': script,
                'collection': collection, 'story_set': story_set,
                'chapter_name': row.get('Title') or row.get('Name') or script,
                'chapter_index': row.get('Index') or row.get('Title'),
                'description': row.get('Desc'), 'open_time': chapter.get('OpenTime'),
                'parent_story_ids': row.get('ParentStoryId', []),
                'sort_key': [chapter.get('OpenTime', '2025-10-20'),
                             {'Story': 0, 'ActivityStory': 1, 'StorySetSection': 2, 'ActivityAvgLevel': 3}[table],
                             row['Id']],
            })
    for row in TABLE.get('DiscIP', {}).values():
        if row.get('AvgId'):
            disc = get('Item', row['Id'])
            contexts[row['AvgId']].append({
                'table': 'DiscIP', 'id': row['Id'], 'script_id': row['AvgId'],
                'collection': '秘纹故事', 'story_set': disc.get('Title'),
                'chapter_name': tr(row.get('StoryName')), 'sort_key': ['2025-10-20', 4, row['Id']],
            })
    for raw in TABLE.get('Plot', {}).values():
        row = tr(raw)
        if not row.get('AvgId'):
            continue
        character = get('Character', row.get('Char')).get('Name', str(row.get('Char')))
        contexts[row['AvgId']].append({
            'table': 'Plot', 'id': row['Id'], 'script_id': row['AvgId'],
            'collection': '旅人逸闻', 'story_set': str(character) + '·旅人故事',
            'chapter_name': row.get('Name'), 'description': row.get('Desc'),
            'sort_key': ['2025-10-20', 3, row['Id']],
        })
    return contexts


def main():
    inventory = load('data/inventory.json')
    rows = [r for r in inventory['entries'] if r['status'] == 'inventoried']
    rows += load('data/audio_variants.json', []) + load('data/supplemental_inventory.json', [])
    state = load('data/export_state.json')
    objects = load('data/wwise_objects.json')
    names = {o['id']: o['objectName'] for o in objects}
    ui_usages = load('data/unity_audio_usages.json', [])
    inferred_names = []
    for text in ['m' + str(n) for n in range(1000)] + [v['VoFile'] for v in TABLE['DiscIP'].values()]:
        h = fnv(text)
        if h not in names:
            names[h] = text
            inferred_names.append({'id': h, 'name': text, 'basis': 'Wwise FNV-1 hash match'})
    for u in ui_usages:
        for text in [u.get('group'), u.get('value'), u.get('event')]:
            if text and fnv(text) not in names:
                names[fnv(text)] = text
    save('data/wwise_hash_names.json', inferred_names)
    context = story_contexts()
    calls = collections.defaultdict(list)
    for p in sorted((LUA / 'Game/UI/Avg/_cn/Config').glob('*.lua')):
        text = p.read_text(encoding='utf8', errors='replace')
        for m in re.finditer(r'cmd\s*=\s*"SetBGM"\s*,\s*param\s*=\s*\{([^}]+)\}', text, re.S):
            params = literals(m[1])
            if len(params) < 4 or params[0] != 0 or not params[3] or params[3] == 'none':
                continue
            call = {'script_id': p.stem, 'path': str(p.relative_to(ROOT)).replace('\\', '/'),
                    'line': text.count('\n', 0, m.start()) + 1,
                    'track': params[2] + 1, 'music_state': params[3], 'params': params,
                    'contexts': context.get(p.stem, [])}
            calls[params[3]].append(call)
    save('data/story_music_calls.json', dict(calls))
    event_rows = load('data/wwise_event_states.json')
    event_by_name = {}
    for e in event_rows:
        if e['event']:
            event_by_name[e['event']] = e  # version overrides installation for identical events
    usage = []
    for table, values in TABLE.items():
        for row in values.values() if isinstance(values, dict) else []:
            if not isinstance(row, dict):
                continue
            for field, value in row.items():
                if 'bgm' not in field.lower() or not isinstance(value, str):
                    continue
                event = event_by_name.get(value)
                if event:
                    usage.append({'table': table, 'id': row.get('Id'), 'field': field,
                                  'event': value, 'event_id': event['event_id'],
                                  'sets': event['sets'], 'config': tr(row)})
    save('data/config_music_usages.json', usage)
    lua_states = []
    for p in LUA.rglob('*.lua'):
        if 'Config' in p.parts:
            continue
        text = p.read_text(encoding='utf8', errors='replace')
        for m in re.finditer(r'(?:SetState|SetSwitch)\(\s*"([^"\n]+)"\s*,\s*"([^"\n]+)"', text):
            if m[1] not in ['system', 'combat', 'level', 'bossType', 'cookie', 'recruit_rarity', 'Disc']:
                continue
            lua_states.append({'group': m[1], 'value': m[2],
                               'path': str(p.relative_to(ROOT)).replace('\\', '/'),
                               'line': text.count('\n', 0, m.start()) + 1,
                               'context': text[max(0, m.start()-150):m.end()+150]})
    save('data/lua_music_states.json', lua_states)
    ip_by_file = {r['VoFile']: tr(r) for r in TABLE['DiscIP'].values()}
    art = {r['disc_code']: r for r in load('data/artwork.json', {}).get('discs', [])}
    tracks = []
    excluded = [r for r in inventory['entries'] if r['status'] != 'inventoried']
    fields = collections.defaultdict(dict)
    for r in rows:
        mapping = state['entries'].get(r['id'], {})
        if mapping.get('status', '').startswith('excluded'):
            excluded.append({'id': r['id'], 'filename': r['filename'], 'status': mapping['status']})
            continue
        render = state['renders'].get(mapping.get('key'), {})
        gs = [{'group_id': g['group_id'], 'group': names.get(g['group_id']),
               'value_id': g['value_id'], 'value': names.get(g['value_id']),
               'name_evidence': 'local audio.unity3d' if g['value_id'] in {o['id'] for o in objects} else 'hash match'}
              for g in r['gamesyncs']]
        values = {g['group']: g['value'] for g in gs}
        for g in gs:
            fields[str(g['group_id'])][str(g['value_id'])] = {'name': g['value']}
        category = r['category']
        title = r['bank']
        detail = {}
        confidence = 'local_wwise_name'
        if category == 'outfit':
            file = values.get('outfit')
            ip = ip_by_file.get(file)
            variant = '凯旋旋律' if values.get('Disc') == 'discVictory' else '核心旋律'
            detail = {'outfit_state': file, 'variant': variant, 'disc_id': ip.get('Id') if ip else None}
            title = f"{get('Item', ip['Id']).get('Title', file) if ip else file}-{variant}"
            confidence = 'local_wwise_plus_mirror_config'
        elif category == 'story':
            bgm = values.get('avg_track1') or values.get('avg_track2')
            occurrences = calls.get(bgm, [])
            candidates = [dict(c, call_line=o['line'], call_path=o['path'])
                          for o in occurrences for c in o['contexts']]
            candidates.sort(key=lambda c: c['sort_key'] + [c['call_line']])
            first = candidates[0] if candidates else None
            first_by_set = {}
            for c in candidates:
                first_by_set.setdefault(str(c['story_set']), c)
            detail = {'music_state': bgm, 'first_appearance_candidate': first,
                      'first_appearance_basis': '配置开放时间、故事类别、章节ID和脚本调用顺序的启发式排序；不同故事线的绝对首次发布时间未证实',
                      'first_by_story_set': list(first_by_set.values()),
                      'script_count': len({o['script_id'] for o in occurrences}),
                      'call_count': len(occurrences), 'call_index': f'data/story_music_calls.json#{bgm}'}
            title = f"{bgm}-" + (f"{first['story_set']}-{first['chapter_name']}" if first else '首次出现待考')
            confidence = 'mirror_script_and_config' if first else 'unresolved_first_appearance'
        elif category == 'combat':
            parts = []
            for group, labels in [('level', LEVEL), ('bossType', BOSS), ('combat', COMBAT), ('system', COMBAT), ('Prologue', {})]:
                value = values.get(group)
                if value:
                    parts.append(labels.get(value, value))
            title = '-'.join(parts) or '战斗音乐'
            detail = {'level': values.get('level'), 'boss_type': values.get('bossType'),
                      'combat_state': values.get('combat'),
                      'boss_name': BOSS.get(values.get('bossType')),
                      'variant_suffix_note': '编号后缀仅证明存在不同状态；阶段、难度等含义须由调用证据进一步确认'}
        else:
            system = values.get('system')
            title = SYSTEM.get(system, system) or ('加载画面' if r['bank'] == 'Music_Loading' else '系统音乐')
            for group in ['cookie', 'recruit_rarity', 'Prologue', 'level']:
                if values.get(group):
                    title += '-' + values[group]
            detail = {'system_state': system}
        if r.get('random_choices'):
            title += '-分支' + '.'.join(map(str, r['random_choices']))
        elif r.get('random'):
            title += '-原始配方'
        relevant = {g['group_id']: g['value_id'] for g in gs
                    if g['group'] in ['system', 'level', 'bossType', 'combat', 'cookie', 'recruit_rarity', 'Prologue']}
        matches = []
        for u in usage:
            event_states = {s['group_id']: s['value_id'] for s in u['sets']}
            common = set(relevant) & set(event_states)
            if common and all(relevant[g] == event_states[g] for g in common):
                matches.append({'table': u['table'], 'id': u['id'], 'event': u['event'],
                                'match': 'all_recipe_fields' if set(relevant) <= set(event_states) else 'partial_fields',
                                'matched_groups': [names.get(g, str(g)) for g in common]})
        direct = [x for x in lua_states if values.get(x['group']) == x['value']]
        unity_matches = []
        for u in ui_usages:
            group, value = u.get('group'), u.get('value')
            if group and value and fnv(group) in relevant and relevant[fnv(group)] == fnv(value):
                unity_matches.append({k: u.get(k) for k in ['bundle', 'path_id', 'game_object', 'group', 'value', 'trigger_type']})
        t = {'id': r['id'], 'title': title, 'category': category,
             'confidence': confidence, 'source': r['source'], 'source_filename': r['filename'],
             'bank': r['bank'], 'event_ids': r['event_ids'],
             'event_names': [names.get(int(v), v) for v in r['event_ids']],
             'gamesyncs': gs, 'wem_ids': r['wem_ids'], 'details': detail,
             'config_usages': matches, 'lua_state_usages': direct,
             'unity_state_usages': unity_matches,
             'render_key': mapping.get('key'), 'status': render.get('status', mapping.get('status', 'missing')),
             'audio_path': render.get('audio_path'), 'pcm_sha256': render.get('pcm_sha256'),
             'parent_id': r.get('parent_id'), 'random_choices': r.get('random_choices'),
             'recipe_path': render.get('recipe_path'), 'supplemental': r['source'].startswith('regenerated')}
        try:
            meta = json.loads(render.get('metadata_raw', '{}'))
        except json.JSONDecodeError:
            meta = {}
        t['audio'] = {'sample_rate': meta.get('sampleRate'), 'channels': meta.get('channels'),
                      'number_of_samples': meta.get('numberOfSamples'), 'loop': meta.get('loopingInfo'),
                      'duration_seconds': meta.get('numberOfSamples', 0) / meta.get('sampleRate', 1)}
        tracks.append(t)
    # Attach AVG aliases to discs by exact decoded audio, then by shared source WEM.
    outfit_tracks = [t for t in tracks if t['category'] == 'outfit']
    for t in tracks:
        if t['category'] != 'story':
            continue
        related = []
        for o in outfit_tracks:
            if t['pcm_sha256'] and t['pcm_sha256'] == o['pcm_sha256']:
                related.append({'disc_id': o['details']['disc_id'], 'track_id': o['id'], 'basis': 'exact_pcm'})
            elif set(t['wem_ids']) & set(o['wem_ids']):
                related.append({'disc_id': o['details']['disc_id'], 'track_id': o['id'], 'basis': 'shared_wem_variant'})
        t['details']['related_outfits'] = related
    # Preserve every route but give files meaningful names and share exact PCM duplicates.
    pcm_paths = {}
    for t in sorted(tracks, key=lambda x: ({'outfit': 0, 'combat': 1, 'system': 2, 'story': 3}[x['category']], x['title'], x['id'])):
        if t['status'] != 'exported':
            continue
        pcm = t['pcm_sha256']
        old = ROOT / t['audio_path']
        if pcm not in pcm_paths:
            folder = {'outfit': '秘纹', 'story': '剧情音乐', 'combat': '战斗音乐', 'system': '系统音乐'}[t['category']]
            dest = ROOT / 'music' / folder / (safe(t['title']) + '--' + pcm[:10] + '.flac')
            dest.parent.mkdir(parents=True, exist_ok=True)
            if old != dest and not dest.exists():
                old.replace(dest)
            pcm_paths[pcm] = str(dest.relative_to(ROOT)).replace('\\', '/')
        t['audio_path'] = pcm_paths[pcm]
        state['renders'][t['render_key']]['audio_path'] = t['audio_path']
    save('data/export_state.json', state)
    save('data/catalog.json', {'schema_version': 1, 'tracks': tracks})
    for category in ['outfit', 'story', 'combat', 'system']:
        save('data/categories/' + category + '.json', {'schema_version': 1, 'tracks': [t for t in tracks if t['category'] == category]})
    discs = []
    for ip in ip_by_file.values():
        item = get('Item', ip['Id'])
        code = ip['VoFile'].split('_')[-1]
        disc_tracks = [t for t in tracks if t['details'].get('disc_id') == ip['Id']]
        a = art.get(code, {})
        discs.append({'id': ip['Id'], 'code': code, 'name': item.get('Title'),
                      'story_title': ip.get('StoryName'), 'story_text': ip.get('StoryDesc'),
                      'literary': item.get('Literary'), 'description': item.get('Desc'),
                      'characters': [get('Character', n).get('Name', n) for n in ip.get('CharId', [])],
                      'music_config': ip, 'disc_config': get('Disc', ip['Id']),
                      'track_ids': [t['id'] for t in disc_tracks],
                      'avg_aliases': [t['id'] for t in tracks if any(x['disc_id'] == ip['Id'] for x in t['details'].get('related_outfits', []))],
                      'artwork': a})
    save('data/categories/outfit_items.json', {'schema_version': 1, 'items': discs})
    save('data/excluded.json', excluded)
    save('data/fields.json', {'groups': [{'id': int(g), 'name': names.get(int(g)), 'values': v} for g, v in fields.items()],
                             'note': '字段原名来自本地Wwise资源；中文用途与后缀解释参考配置及Lua，未证实的数值后缀不等同于阶段或难度。'})
    summary = {'source_txtp': len(inventory['entries']), 'source_non_transition': inventory['counts'].get('inventoried'),
               'excluded': len(excluded), 'catalog_routes': len(tracks),
               'random_branch_routes': len(load('data/audio_variants.json', [])),
               'supplemental_routes': len(load('data/supplemental_inventory.json', [])),
               'by_category': dict(collections.Counter(t['category'] for t in tracks)),
               'export_status': dict(collections.Counter(t['status'] for t in tracks)),
               'unique_pcm': len(pcm_paths), 'outfit_items': len(discs),
               'story_routes_with_first_appearance': sum(t['category'] == 'story' and bool(t['details'].get('first_appearance_candidate')) for t in tracks),
               'config_usages': len(usage), 'story_music_states': len(calls),
               'artwork_images': sum(len(d['artwork'].get('images', [])) for d in discs)}
    save('data/summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
