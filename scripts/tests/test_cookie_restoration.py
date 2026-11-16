from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restore_cookie_music import restore, COOKIE_GROUP


class CookieRestorationTests(unittest.TestCase):
    def test_restore_short_cues_deduplicates_content_and_keeps_user_edits(self):
        mapping = {'groups': [{'id': COOKIE_GROUP, 'name': 'Custom heading', 'date': '2030-01-01',
                               'description': 'User text', 'tracks': []}]}
        metadata = {'groups': [{'id': COOKIE_GROUP, 'name': '甜心梦工坊', 'date': '', 'track_ids': []}], 'tracks': []}
        def cue(identifier, state, duration):
            return {'id': identifier, 'title': state, 'category': 'system', 'source_states': [{'value': state}],
                    'duration_seconds': duration, 'sample_rate': 44100, 'channels': 2,
                    'number_of_samples': int(44100*duration), 'loop': None}
        contents = {'contents': [cue('short', 'cookie_start', 8), cue('long', 'cookie4', 80), cue('unrelated', 'main', 9)]}
        actual, technical, added = restore(mapping, metadata, contents)
        self.assertEqual([t['id'] for t in actual['groups'][0]['tracks']], ['short'])
        self.assertEqual(actual['groups'][0]['description'], 'User text')
        self.assertEqual(actual['groups'][0]['name'], 'Custom heading')
        self.assertEqual(actual['groups'][0]['minimum_duration_seconds'], 0)
        again, _, new = restore(actual, technical, contents)
        self.assertEqual(again, actual)
        self.assertEqual(new, [])


if __name__ == '__main__':
    unittest.main()
