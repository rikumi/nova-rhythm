import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cookie_order import cue_order


class CookieOrderTests(unittest.TestCase):
    def cue(self, variant, *states):
        return {'source_states': [{'group': 'system', 'value': variant}]+[{'group': 'cookie', 'value': value} for value in states]}

    def test_variants_and_speed_progression(self):
        slow = self.cue('cookie2', 'cookie_bpm40')
        fast = self.cue('cookie2', 'cookie_bpm75')
        first = self.cue('cookie', 'cookie_bpm75')
        self.assertLess(cue_order(first), cue_order(slow))
        self.assertLess(cue_order(slow), cue_order(fast))
        self.assertLess(cue_order(self.cue('cookie2', 'cookie_start')), cue_order(slow))
        self.assertGreater(cue_order(self.cue('cookie2', 'cookie_free')), cue_order(fast))

    def test_shared_menu_and_deduplicated_speed_free_end(self):
        self.assertEqual(cue_order(self.cue('cookie4', 'None')), (0, -1, 0))
        self.assertEqual(cue_order(self.cue('cookie3', 'cookie_bpm60', 'cookie_free', 'cookie_end')), (3, 1, 60))
