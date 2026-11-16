"""Order story cues by configured chapter and script call position, without numeric title prefixes."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re

from pipeline_paths import REPOSITORY, GAME, protect_output

PREFIX = re.compile(r'^\s*剧情配乐\s*\d+\s*(?:[·・:：—-]\s*)?')
SCENE_QUOTE = re.compile(r'\s*·\s*「[^」]*」')
TRACK_SUFFIX = re.compile(r'\s*·\s*(?:第[一二三四五六七八九十\d]+音轨|音轨\s*[\d/]+)$')


def title_base(name):
    return TRACK_SUFFIX.sub('', SCENE_QUOTE.sub('', PREFIX.sub('', name))).strip(' ·')


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def context_key(context):
    order = context.get('sort_key', ['', 9, context.get('id', 0)])
    return (str(order[0] or ''), int(order[1]), int(context.get('chapter_order', order[2])), int(context.get('call_line', 0)))


def chapter_orders(tables):
    """ActivityStoryDataBase.SortStoryList uses breadth-first parent traversal."""
    entries, hashes = [], {}
    for table, chapter_field in [('Story', 'Chapter'), ('ActivityStory', 'ChapterId'),
                                  ('StorySetSection', 'ChapterId'), ('ActivityAvgLevel', 'ActivityId'), ('Plot', 'Char')]:
        path = tables/(table+'.json')
        if not path.exists():
            continue
        import hashlib
        hashes[table] = hashlib.sha256(path.read_bytes()).hexdigest()
        groups = {}
        for row in load(path).values():
            groups.setdefault(str(row.get(chapter_field, '')), []).append(row)
        rank = 0
        for _, rows in sorted(groups.items(), key=lambda item: (len(item[0]), item[0])):
            rows.sort(key=lambda row: row['Id'])
            ordered = rows
            if table == 'ActivityStory':
                by_script = {r.get('StoryId') or r.get('AvgLuaName'): r for r in rows}
                roots, children = [], {}
                for script, row in by_script.items():
                    parents = row.get('ParentStoryId') or []
                    if isinstance(parents, str):
                        parents = [parents]
                    parents = [p for p in parents if p]
                    if not parents:
                        roots.append(script)
                    for parent in parents:
                        children.setdefault(parent, []).append(script)
                order = lambda script: by_script[script]['Id']
                queue = sorted(roots, key=order); seen = set(queue); ordered = []
                for script in queue:
                    ordered.append(by_script[script])
                    for child in sorted(children.get(script, []), key=order):
                        if child not in seen:
                            seen.add(child); queue.append(child)
                ordered += [r for r in rows if (r.get('StoryId') or r.get('AvgLuaName')) not in seen]
            for row in ordered:
                entries.append({'table': table, 'id': row['Id'], 'chapter': row.get(chapter_field), 'rank': rank})
                rank += 1
    return {'schema_version': 1, 'source_table_sha256': hashes,
            'logic': {'mainline': 'GameCore/Data/DataClass/AvgData.lua: Init CFG_ChapterStoryNumIds, config order',
                      'activity': 'GameCore/Data/DataClass/Activity/ActivityStoryDataBase.lua: SortStoryList, BFS roots/children by Id'},
            'entries': entries}


def set_key(context):
    return (context.get('collection', ''), context.get('story_set', ''))


def scene_quote(lua_dir, context, cache):
    """Use actual nearby dialogue, never an invented mood or plot description."""
    if not lua_dir:
        return None
    path = lua_dir/(context['script_id']+'.lua')
    if not path.is_file():
        return None
    if path not in cache:
        cache[path] = path.read_text(encoding='utf8', errors='replace').splitlines()
    start = context.get('call_line', 1)
    text = '\n'.join(cache[path][start:start+3000])
    # Don't borrow dialogue after a subsequent music change.
    text = re.split(r'cmd\s*=\s*"SetBGM"', text, maxsplit=1)[0]
    for match in re.finditer(r'cmd\s*=\s*"SetTalk"\s*,\s*param\s*=\s*\{(.*?)\}', text, re.S):
        strings = re.findall(r'"(?:\\.|[^"\\])*"', match[1])
        if len(strings) < 2:
            continue
        try:
            quote = json.loads(strings[1])
        except ValueError:
            continue
        cleaned = re.sub(r'==[^=]+==|<[^>]+>', '', quote)
        for clause in re.split(r'[，,。！？!?；;\n]|…+|\.{2,}', cleaned):
            clause = clause.strip(' \t「」“”\"：:—-')
            if len(clause) >= 5 and not re.search(r'^[A-Za-z0-9_/]+$', clause):
                clause = clause.replace('“', '').replace('”', '')
                return {'text': quote, 'caption': clause[:18]+('…' if len(clause) > 18 else '')}
    return None


def arrange(mapping, metadata, contents, catalog, calls, lua_dir=None, prior_report=None, chapter_order=None):
    result = copy.deepcopy(mapping)
    by_file = {t['path']: t for t in metadata['tracks']}
    by_content = {c['id']: c for c in contents['contents']}
    by_route = {r['id']: r for r in catalog['tracks']}
    ranks = {(r['table'], r['id']): r['rank'] for r in (chapter_order or {}).get('entries', [])}
    def ranked(context):
        if (context['table'], context['id']) in ranks:
            return dict(context, chapter_order=ranks[context['table'], context['id']])
        return context
    old_quotes = {}
    for group in (prior_report or {}).get('groups', []):
        for row in group['tracks']:
            context = row.get('first_appearance')
            if context and row.get('scene_quote'):
                old_quotes[context['script_id'], context['call_line']] = row['scene_quote']
    cache, report_groups = {}, []
    for group in result['groups']:
        records, votes = [], Counter()
        for index, entry in enumerate(group.get('tracks', [])):
            old = by_file.get(entry['file'], {})
            identifier = old.get('id') or entry.get('id')
            content = by_content.get(identifier, {})
            routes = [by_route[r] for r in content.get('route_ids', []) if r in by_route]
            states = sorted({r.get('details', {}).get('music_state') for r in routes if r.get('details', {}).get('music_state')})
            contexts, seen = [], set()
            for state in states:
                for call in calls.get(state, []):
                    for context in call['contexts']:
                        key = (context['table'], context['id'], call['line'])
                        if key in seen:
                            continue
                        seen.add(key)
                        contexts.append(ranked(dict(context, call_line=call['line'], call_path=call['path'], music_state=state)))
            firsts = [r.get('details', {}).get('first_appearance_candidate') for r in routes]
            firsts = [ranked(c) for c in firsts if c]
            if firsts:
                votes[set_key(min(firsts, key=context_key))] += 1
            records.append({'index': index, 'entry': entry, 'id': identifier, 'content': content,
                            'routes': routes, 'states': states, 'contexts': contexts or firsts})
        # A group can also include character side stories or reused cues. Prefer
        # appearances in this group's own story set before cross-story candidates.
        dominant = votes.most_common(1)[0][0] if votes else None
        audit, story_slots = [], []
        for record in records:
            entry, content = record['entry'], record['content']
            contexts = record['contexts']
            local = [c for c in contexts if set_key(c) == dominant]
            first = min(local or contexts, key=context_key) if contexts else None
            is_story = 'story' in content.get('categories', [])
            original_name = entry['name']
            base = PREFIX.sub('', original_name).strip(' ·')
            quote = scene_quote(lua_dir, first, cache) if first else None
            if first and not quote:
                quote = old_quotes.get((first['script_id'], first['call_line']))
            channels = sorted({int(m[1]) for r in record['routes'] for g in r.get('gamesyncs', [])
                               if (m := re.fullmatch(r'avg_track(\d+)', str(g.get('group', ''))))})
            if is_story and first and (PREFIX.match(original_name) or original_name in {first.get('story_set'), group['name']}):
                parts = [first.get('story_set'), first.get('chapter_name')]
                entry['name'] = ' · '.join(dict.fromkeys(p for p in parts if p))
            elif PREFIX.match(original_name):
                entry['name'] = base
                if record['states'] and ('待考' in base or '未识别' in base):
                    entry['name'] += ' · '+ '/'.join(record['states'])
            elif original_name == group['name'] or re.fullmatch(r'主线第[一二三四五六七八九十\d]+章', original_name):
                category = content.get('category')
                if category in ['system', 'combat']:
                    entry['name'] += ' · '+('界面配乐' if category == 'system' else '战斗配乐')
            # Only reorder story positions; keep non-story music and outfit links
            # in their existing relative positions. Unknown positions stay last.
            if is_story:
                story_slots.append(record)
            audit.append({'audio_id': record['id'], 'file': entry['file'], 'old_name': original_name,
                          'name': entry['name'], 'is_story': is_story,
                          'first_appearance': first, 'scene_quote': quote,
                          'order_key': [0 if local else 1, *context_key(first)] if first else None})
        ordered = sorted(story_slots, key=lambda r: (
            0 if r['contexts'] and any(set_key(c) == dominant for c in r['contexts']) else 1,
            min((context_key(c) for c in r['contexts'] if set_key(c) == dominant), default=
                min((context_key(c) for c in r['contexts']), default=('9999', 99, 10**12, 10**12))), r['index']))
        for slot, record in zip([r['index'] for r in story_slots], ordered):
            group['tracks'][slot] = record['entry']
        # Titles use chapter/scene names only. Number same-name cues after all
        # dialogue captions and obsolete channel suffixes have been removed.
        bases = {r['entry']['file']: title_base(r['entry']['name']) for r in story_slots}
        counts, seen_titles = Counter(bases.values()), Counter()
        for entry in group['tracks']:
            if entry['file'] not in bases:
                continue
            base = bases[entry['file']]
            seen_titles[base] += 1
            entry['name'] = base+(f' · 第{seen_titles[base]}音轨' if counts[base] > 1 else '')
        final_names = {entry['file']: entry['name'] for entry in group['tracks']}
        for row in audit:
            row['name'] = final_names[row['file']]
        report_groups.append({'group_id': group['id'], 'name': group['name'],
                              'dominant_story_set': dominant, 'tracks': audit,
                              'ordered_story_files': [r['entry']['file'] for r in ordered]})
    return result, {'schema_version': 1,
                    'policy': 'Story configuration chapter order + SetBGM script line; prefer the current story set; branch ties follow configuration order. No dialogue captions in names. Same-base names get sequential track suffixes after ordering. Non-story positions and user descriptions are preserved.',
                    'groups': report_groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, default=REPOSITORY/'public/data/story-melodies.json')
    parser.add_argument('--lua-dir', type=Path, help='Directory containing Chinese AVG Lua scripts; optional dialogue captions.')
    parser.add_argument('--tables-dir', type=Path, help='Refresh configured chapter ordering from mirrored CN/bin tables.')
    parser.add_argument('--report', type=Path, default=REPOSITORY/'.build/story-music-order.json')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    protect_output(args.mapping, GAME); protect_output(args.report, GAME)
    reference = REPOSITORY/'references/analysis'
    prior = REPOSITORY/'references/story-music-order.json'
    order_path = REPOSITORY/'references/story-chapter-order.json'
    if args.tables_dir:
        save(order_path, chapter_orders(args.tables_dir))
    result, report = arrange(load(args.mapping), load(REPOSITORY/'public/data/library.json'),
                             load(reference/'content_groups.json'), load(reference/'catalog.json'),
                             load(reference/'story_music_calls.json'), args.lua_dir,
                             load(prior) if prior.exists() else None,
                             load(order_path) if order_path.exists() else None)
    save(args.report, report)
    if args.apply:
        save(args.mapping, result)
    changes = sum(t['name'] != t['old_name'] for g in report['groups'] for t in g['tracks'])
    ordered = sum(len(g['ordered_story_files']) for g in report['groups'])
    print(f'Story cues ordered: {ordered}; titles updated: {changes}; report: {args.report}')


if __name__ == '__main__':
    main()
