from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deduplicate_event_themes import compare


class EventThemeDedupTests(unittest.TestCase):
    def test_only_verified_system_bgm_matches_are_removed(self):
        evidence = {'entries': [{'group_id': 'activity-1', 'name': 'Event', 'status': 'unique_shop_outfit',
                                 'candidates': [{'outfit_id': 1, 'name': 'Free disc', 'code': '1'}]}]}
        outfit = {'items': [{'id': 1, 'music': [{'id': 'core', 'title': '核心旋律', 'duration_seconds': 90}]}]}
        tracks = [{'id': identifier, 'path': '/'+identifier+'.opus', 'duration_seconds': duration}
                  for identifier, duration in [('core', 90), ('prefix', 100), ('different', 100), ('combat', 100), ('short', 30)]]
        library = {'tracks': tracks}
        mapping = {'groups': [{'id': 'activity-1', 'name': 'Event', 'tracks': [{'name': t['id'], 'file': t['path']} for t in tracks]}]}
        contents = {'contents': [{'id': t['id'], 'categories': ['combat'] if t['id'] == 'combat' else ['system']} for t in tracks]}
        fingerprints = {'core': 'same', 'prefix': 'same', 'different': 'different', 'combat': 'same'}
        report = compare(evidence, mapping, library, outfit, contents, lambda identifier: identifier, fingerprints.__getitem__)
        self.assertEqual(report['errors'], [])
        self.assertEqual([(r['audio_id'], r['match']) for r in report['removed']],
                         [('core', 'identical_full_pcm'), ('prefix', 'identical_first_60_seconds_pcm')])

    def test_recorded_removals_have_equal_prefix_fingerprints_and_shop_evidence(self):
        import json
        root = Path(__file__).resolve().parents[2]
        report = json.loads((root/'references/activity-theme-dedup.json').read_text(encoding='utf8'))
        evidence = json.loads((root/'references/activity-main-outfits.json').read_text(encoding='utf8'))
        events = {e['group_id']: e for e in evidence['entries']}
        self.assertEqual(report['errors'], [])
        for decision in report['removed']:
            event = events[decision['group_id']]
            self.assertEqual(event['status'], 'unique_shop_outfit')
            self.assertEqual(event['candidates'][0]['outfit_id'], decision['main_outfit']['outfit_id'])
            if decision['match'] == 'identical_first_60_seconds_pcm':
                self.assertEqual(decision['activity_prefix_sha256'], decision['main_prefix_sha256'])


if __name__ == '__main__':
    unittest.main()
