from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from permanent_library import reorganize, mode_candidates
from story_mapping import ordered_groups


class PermanentLibraryTests(unittest.TestCase):
    def test_explicit_exploration_themes_win_over_reuse_by_other_modes(self):
        target, reasons = mode_candidates({'name': '流水与暗影'}, 'mode-灾变防线',
                                         {'source_states': [{'group': 'level', 'value': 'zombieForest'}]}, [])
        self.assertEqual(target, 'mode-星塔探索')
        self.assertIn('mode-灾变防线', reasons)

    def test_verified_floor_references_and_real_traveler_duel_name(self):
        target, _ = mode_candidates({'name': 'Boss'}, 'activity-1', {},
                                    [{'config_usages': [{'table': 'ScoreBossFloor', 'id': 1, 'event': 'boss', 'match': 'all_recipe_fields'}]}])
        self.assertEqual(target, 'mode-联合讨伐')
        target, _ = mode_candidates({'name': 'Boss'}, 'permanent-combat',
                                    {'source_states': [{'group': 'level', 'value': 'travelerDuel'}]}, [])
        self.assertEqual(target, 'mode-巅峰秀场')

    def test_modes_move_before_catch_all_preserving_user_metadata(self):
        mapping = {'groups': [{'id': 'permanent-system', 'name': 'System', 'date': '', 'tracks': []},
                               {'id': 'permanent-combat', 'name': 'Other', 'date': '', 'tracks': [
                                   {'name': '心危擂台', 'file': '/audio/tower.opus', 'description': 'Keep user note'}]}]}
        metadata = {'tracks': [{'id': 'tower', 'path': '/audio/tower.opus'}]}
        content = {'contents': [{'id': 'tower', 'route_ids': [], 'source_states': [{'group': 'level', 'value': 'endlessTower'}]}]}
        actual, _ = reorganize(mapping, metadata, content, {'tracks': []})
        groups = ordered_groups(actual['groups'])
        self.assertEqual([g['id'] for g in groups], ['permanent-system', 'mode-心危擂台', 'permanent-combat'])
        self.assertEqual(groups[1]['tracks'][0]['description'], 'Keep user note')
