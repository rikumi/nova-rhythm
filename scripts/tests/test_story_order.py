import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from order_story_music import arrange, chapter_orders, scene_quote


class StoryOrderTests(unittest.TestCase):
    def test_chapter_then_script_order_preserves_nonstory_slots_and_user_descriptions(self):
        def context(identifier):
            return {'table': 'Story', 'id': identifier, 'script_id': 'chapter-'+str(identifier),
                    'collection': 'Collection', 'story_set': 'Chapter', 'chapter_name': 'Scene '+str(identifier),
                    'sort_key': ['2026-01-01', 0, identifier]}
        cues = [('late', 'm1', 2, 10), ('middle', 'm2', 1, 90), ('early', 'm99', 1, 20)]
        metadata, contents, catalog, calls = {'tracks': []}, {'contents': []}, {'tracks': []}, {}
        for identifier, state, chapter, line in cues:
            metadata['tracks'].append({'id': identifier, 'path': '/'+identifier+'.opus'})
            contents['contents'].append({'id': identifier, 'category': 'story', 'categories': ['story'], 'route_ids': [identifier]})
            catalog['tracks'].append({'id': identifier, 'details': {'music_state': state, 'first_appearance_candidate': dict(context(chapter), call_line=line)}})
            calls[state] = [{'line': line, 'path': 'script.lua', 'contexts': [context(chapter)]}]
        tracks = [{'name': '剧情配乐 1 · Scene', 'file': '/'+identifier+'.opus', 'description': 'User text'} for identifier in ['late', 'middle', 'early']]
        tracks.insert(1, {'name': 'Combat', 'file': '/combat.opus', 'description': 'Keep me'})
        mapping = {'schema_version': 1, 'groups': [{'id': 'group', 'name': 'Group', 'date': '2030-01-01', 'description': 'Keep group text', 'tracks': tracks}]}
        actual, report = arrange(mapping, metadata, contents, catalog, calls)
        group = actual['groups'][0]
        self.assertEqual([t['file'] for t in group['tracks']], ['/early.opus', '/combat.opus', '/middle.opus', '/late.opus'])
        self.assertEqual(group['description'], 'Keep group text')
        self.assertTrue(all(t['description'] in ['User text', 'Keep me'] for t in group['tracks']))
        self.assertTrue(all(not t['name'].startswith('剧情配乐') for t in group['tracks']))
        self.assertEqual(report['groups'][0]['ordered_story_files'], ['/early.opus', '/middle.opus', '/late.opus'])
        self.assertEqual(group['tracks'][0]['name'], 'Chapter · Scene 1 · 第1音轨')
        self.assertEqual(group['tracks'][2]['name'], 'Chapter · Scene 1 · 第2音轨')
        self.assertEqual(group['tracks'][3]['name'], 'Chapter · Scene 2')

    def test_activity_branch_order_matches_game_breadth_first_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = {str(i): {'Id': i, 'ChapterId': 1, 'StoryId': str(i), 'ParentStoryId': parents}
                    for i, parents in [(1, []), (2, ['1']), (3, ['2']), (10, [])]}
            (root/'ActivityStory.json').write_text(json.dumps(rows), encoding='utf8')
            self.assertEqual([r['id'] for r in chapter_orders(root)['entries']], [1, 10, 2, 3])

    def test_caption_is_real_dialogue_before_next_music_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = '\n'.join(['-- music command', 'cmd = "SetTalk", param = {0, "speaker", "炮击阵地准备完毕，委员长！"}',
                              'cmd = "SetBGM"', 'cmd = "SetTalk", param = {0, "speaker", "不应借用后面的对白"}'])
            (root/'scene.lua').write_text(text, encoding='utf8')
            quote = scene_quote(root, {'script_id': 'scene', 'call_line': 1}, {})
            self.assertEqual(quote['caption'], '炮击阵地准备完毕')
            self.assertEqual(quote['text'], '炮击阵地准备完毕，委员长！')


if __name__ == '__main__':
    unittest.main()
