import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuild
from story_mapping import apply_mapping, to_mapping


class StoryMappingTests(unittest.TestCase):
    def test_mapping_matches_reviewed_catalog_and_references_existing_files(self):
        root = rebuild.REPOSITORY/'public'
        mapping = rebuild.read(root/'data/story-melodies.json')
        catalog = rebuild.read(root/'data/library.json')
        resolved = apply_mapping(mapping, catalog)
        self.assertEqual(len(resolved['tracks']), sum(len(g['tracks']) for g in mapping['groups']))
        for group in mapping['groups']:
            for track in group['tracks']:
                if not track['file'].startswith('https://'):
                    self.assertTrue((root/track['file'].lstrip('/')).is_file(), track['file'])

    def test_deleted_track_is_not_rediscovered_and_descriptions_survive_rebuild(self):
        songs = [{'id': 'audio-'+str(i)*64, 'title': 'Song '+str(i), 'path': '/audio/fixture-'+str(i)+'.opus',
                  'group_id': 'fixture', 'sample_rate': 44100, 'channels': 2, 'number_of_samples': 3969000,
                  'duration_seconds': 90, 'loop': None, 'uses': [], 'aliases': [], 'source_title': 'raw'} for i in range(2)]
        metadata = {'schema_version': 2, 'groups': [{'id': 'fixture', 'name': 'Fixture', 'date': '',
                     'track_ids': [s['id'] for s in songs], 'outfit_references': []}], 'tracks': songs}
        mapping = to_mapping(metadata)
        group = mapping['groups'][0]
        deleted = group['tracks'].pop()
        group.update(name='Reviewed group', date='2030-01-01', description='Group description')
        group['tracks'][0].update(name='Reviewed song', description='Song description')
        by_file = {t['path']: t for t in metadata['tracks']}
        songs = [by_file[deleted['file']], by_file[group['tracks'][0]['file']]]
        rows = [{'id': 'route-'+str(i), 'source': 'version', 'filename': 'Music_AVG.txtp', 'bank': 'Music_AVG',
                 'category': 'story', 'gamesyncs': [], 'status': 'exported', 'pcm_sha256': t['id'][6:],
                 'audio': {k: t[k] for k in ['sample_rate', 'channels', 'number_of_samples', 'duration_seconds', 'loop']}}
                for i, t in enumerate(songs)]
        original_read = rebuild.read
        def read(path, default=None):
            if path.name == 'story-melodies.json':
                return mapping
            if path.name == 'library.json':
                return metadata
            return original_read(path, default)
        with patch.object(rebuild, 'read', side_effect=read):
            _, library, _, published = rebuild.build_manifests(rows, {}, False)
        self.assertNotIn(by_file[deleted['file']]['id'], published)
        exported = next(g for g in to_mapping(library)['groups'] if g['id'] == group['id'])
        self.assertEqual(exported['name'], 'Reviewed group')
        self.assertEqual(exported['date'], '2030-01-01')
        self.assertEqual(exported['description'], 'Group description')
        self.assertEqual(exported['tracks'][0]['name'], 'Reviewed song')
        self.assertEqual(exported['tracks'][0]['description'], 'Song description')


if __name__ == '__main__':
    unittest.main()
