from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apply_qqmusic_names import official_name, renamed


class OfficialNameTests(unittest.TestCase):
    def test_name_format_is_idempotent_and_equal_names_are_unchanged(self):
        self.assertEqual(official_name('New', 'Old'), 'New（Old）')
        self.assertEqual(official_name('New', 'New（Old）'), 'New（Old）')
        self.assertEqual(official_name('New', 'New'), 'New')

    def test_only_verified_titles_change_without_reintroducing_deleted_tracks(self):
        evidence = {'verified': True, 'waveform_median': .99, 'waveform_checks': [{'correlation': .99}, {'correlation': .99}]}
        matches = {'matches': [{'audio_id': 'audio-one', 'official_title': 'Official', 'qq_mid': 'qq-one', 'evidence': evidence},
                               {'audio_id': 'audio-deleted', 'official_title': 'Deleted', 'qq_mid': 'qq-two', 'evidence': evidence}]}
        stories = {'groups': [{'id': 'group', 'name': 'Group', 'date': '2030-01-01', 'description': 'User text',
                               'tracks': [{'name': 'Original', 'file': '/audio/audio-one.opus', 'description': 'Keep me'}]}]}
        outfits = {'items': []}
        result, _, changes = renamed(stories, outfits, matches)
        self.assertEqual(result['groups'][0]['tracks'][0]['name'], 'Official（Original）')
        self.assertEqual(result['groups'][0]['description'], 'User text')
        self.assertEqual(result['groups'][0]['tracks'][0]['description'], 'Keep me')
        self.assertEqual(len(changes), 1)
        self.assertEqual(len(result['groups'][0]['tracks']), 1)
        matches['matches'][0]['evidence'] = {'verified': False}
        with self.assertRaises(ValueError):
            renamed(stories, outfits, matches)
