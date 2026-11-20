from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from audit_music_duplicates import assess, protected_variant_pair
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'Optional audio analysis dependencies')
class MusicDuplicateTests(unittest.TestCase):
    def checks(self, values=(.91, .93, .92), offsets=(.1, .1, .1)):
        return {'waveform_checks': [{'correlation': v, 'verified_offset_seconds': o} for v,o in zip(values,offsets)],
                'waveform_median': sorted(values)[1], 'offset_seconds': 0}

    def test_relaxed_gain_mix_tolerance_still_requires_all_windows_and_stable_alignment(self):
        self.assertTrue(assess(self.checks(), 90, 90, True)['eligible'])
        self.assertFalse(assess(self.checks((.03,.99,.99)), 90, 90, True)['eligible'])
        self.assertFalse(assess(self.checks(offsets=(0,.1,.2)), 90, 90, True)['eligible'])

    def test_a_shared_short_segment_cannot_remove_a_longer_recording(self):
        self.assertFalse(assess(self.checks(), 90, 20, True)['eligible'])
        self.assertTrue(assess(self.checks(), 20, 90, True)['eligible'])

    def test_game_tempo_and_free_play_variants_remain_separate(self):
        self.assertTrue(protected_variant_pair({'group_id':'mode-甜心梦工坊'}, {'group_id':'mode-甜心梦工坊'}))
        self.assertFalse(protected_variant_pair({'group_id':'activity-x'}, {'group_id':'activity-x'}))


class DuplicateCatalogTests(unittest.TestCase):
    def test_reviewed_removals_have_a_surviving_preferred_recording(self):
        root = Path(__file__).resolve().parents[2]
        read = lambda p: json.loads((root/p).read_text(encoding='utf8'))
        mapping = read('public/data/story-melodies.json')
        report = read('references/music-duplicate-review.json')
        files = {t['file'] for g in mapping['groups'] for t in g['tracks']}
        files.update(t['path'] for o in read('public/data/outfits.json')['items'] for t in o['music'])
        for removed in report['removed']:
            self.assertNotIn(removed['entry']['file'], files)
            candidates = [r for r in report['results'] if r['eligible'] and r['remove']['id']==removed['audio_id']]
            canonical = min(candidates, key=lambda r:r['keep']['priority'])
            self.assertIn(canonical['keep']['path'], files)
            self.assertLess(canonical['keep']['priority'],canonical['remove']['priority'])
        boss = 'audio-257bad628dc942ea833c91fcda17d43ecbdec487b86acf6fa33361a18357320b'
        self.assertIn('/audio/'+boss+'.opus',files)
        for identifier in ['audio-10ada5e100bb793416ea648e56a2898e9dd04048cd6cd5185afd75e2628f1813',
                           'audio-5ecf192bbaa0729c9f1f769658312ddcadf25d1cb33d795ff278755755c72a07']:
            self.assertNotIn('/audio/'+identifier+'.opus',files)
