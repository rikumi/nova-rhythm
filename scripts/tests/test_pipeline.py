import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuild
from pipeline_paths import protect_output


class PipelineTests(unittest.TestCase):
    def test_recipe_relocation_and_comments(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp).resolve()/'game with spaces'
            parent = game/'txtp'; parent.mkdir(parents=True)
            recipe, dependencies = rebuild.portable_recipe('# source: other.bnk\nwem/123.wem #i #b 12\ngroup = -S1 #@loop\n', parent, game)
            self.assertEqual(recipe, '{{GAME}}/txtp/wem/123.wem #i #b 12\ngroup = -S1 #@loop\n')
            self.assertEqual(dependencies, [parent/'wem/123.wem'])
            with self.assertRaises(ValueError):
                rebuild.portable_recipe('../../outside.wem', parent, game)

    def test_disjoint_outputs(self):
        game = Path(tempfile.gettempdir()).resolve()/'game'
        for output in [game, game/'generated', game.parent]:
            with self.assertRaises(ValueError):
                protect_output(output, game)

    def test_scan_excludes_transition_state_and_expands_random(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); refs = root/'refs'; refs.mkdir()
            (refs/'routes.json').write_text('{"entries": []}', encoding='utf8')
            bank = root/'game'/rebuild.SOURCE_DIRS['install']; bank.mkdir(parents=True)
            (bank/'Music_AVG (1=2).txtp').write_text('wem/1.wem #i\n', encoding='utf8')
            (bank/'Music_Combat {r}.txtp').write_text('wem/2.wem\nwem/3.wem\ngroup = -R2>-\n', encoding='utf8')
            with patch.object(rebuild, 'REFS', refs):
                rows, errors = rebuild.scan(root/'game', {1: 'state', 2: 'transition'})
            self.assertEqual(errors, [])
            self.assertEqual(sum(r['status'] == 'excluded_transition' for r in rows), 1)
            eligible = [r for r in rows if r['status'] == 'inventoried']
            self.assertEqual(len(eligible), 3)
            branches = [r for r in eligible if r.get('parent_id')]
            self.assertEqual({r['random_choices'][0] for r in branches}, {1, 2})
            self.assertTrue(any('>-\n' in r['recipe'] for r in eligible))

    def row(self, pcm, seconds=90, **extra):
        return {'id': 'new-route', 'source': 'version', 'filename': 'Music_AVG (1=99).txtp', 'bank': 'Music_AVG',
                'category': 'story', 'gamesyncs': [], 'status': 'exported', 'pcm_sha256': pcm,
                'audio': {'sample_rate': 44100, 'channels': 2, 'number_of_samples': int(seconds*44100),
                          'duration_seconds': seconds, 'loop': None}, **extra}

    def test_unknown_names_dedup_duration_and_annotation(self):
        pcm = '0'*64
        row = self.row(pcm)
        duplicate = row | {'id': 'another-route', 'filename': 'Music_System (2=99).txtp', 'bank': 'Music_System'}
        _, library, pending, published = rebuild.build_manifests([row, duplicate, self.row('1'*64, 30)], {}, False)
        self.assertEqual(len(library['tracks']), 1)
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(published), 1)
        self.assertEqual(library['tracks'][0]['title'], row['filename'][:-5])
        self.assertEqual(len(library['tracks'][0]['aliases']), 2)
        annotations = {'tracks': {'audio-'+pcm: {'title': 'Verified title', 'group': {'id': 'activity-new', 'name': 'Activity', 'date': '2027-01-01'}}}}
        _, library, _, _ = rebuild.build_manifests([row], annotations, False)
        self.assertEqual(library['tracks'][0]['title'], 'Verified title')
        self.assertEqual(library['groups'][0]['id'], 'activity-new')

    def test_known_outfit_short_music_and_first_release_links(self):
        outfits = rebuild.read(rebuild.REPOSITORY/'public/data/outfits.json')['items']
        outfit = outfits[0]; music = outfit['music'][0]
        row = self.row(music['id'][6:], 20)
        exported, library, pending, _ = rebuild.build_manifests([row, copy.deepcopy(row)], {}, False)
        self.assertEqual(len(exported['items']), 1)
        self.assertEqual(exported['items'][0]['id'], outfit['id'])
        self.assertEqual(len(exported['items'][0]['music']), 1)
        self.assertEqual(library['tracks'], [])
        self.assertTrue(any(r['outfit_id'] == outfit['id'] for g in library['groups'] for r in g['outfit_references']))
        reversed_rows = [self.row(m['id'][6:], 20) for m in reversed(outfit['music'])]
        exported, _, _, _ = rebuild.build_manifests(reversed_rows, {}, False)
        self.assertEqual([m['id'] for m in exported['items'][0]['music']], [m['id'] for m in outfit['music']])

    def test_new_outfit_raw_state_keeps_victory_under_one_minute(self):
        states = [{'group': 'outfit', 'value': 'outfit_99999'}, {'group': 'Disc', 'value': 'discVictory'}]
        outfits, library, pending, published = rebuild.build_manifests([self.row('2'*64, 15, gamesyncs=states)], {}, False)
        self.assertEqual(outfits['items'][0]['name'], 'outfit_99999')
        self.assertEqual(outfits['items'][0]['music'][0]['title'], '凯旋旋律')
        self.assertEqual(len(published), 1)
        self.assertEqual(library['tracks'], [])

    def test_reviewed_catalog_preserves_order_and_canonical_loops(self):
        outfits = rebuild.read(rebuild.REPOSITORY/'public/data/outfits.json')
        library = rebuild.read(rebuild.REPOSITORY/'public/data/library.json')
        songs = library['tracks']+[m for o in outfits['items'] for m in o['music']]
        fields = ['sample_rate', 'channels', 'number_of_samples', 'duration_seconds', 'loop']
        rows = []
        for song in reversed(songs):
            audio = {k: copy.deepcopy(song[k]) for k in fields}
            if audio['loop']:
                audio['loop']['start'] = 0  # Simulate an identical alias with a different loop anchor.
            rows.append(self.row(song['id'][6:], audio=audio))
        actual_outfits, actual_library, pending, _ = rebuild.build_manifests(rows, {}, False)
        self.assertEqual(actual_outfits, outfits)
        self.assertEqual(actual_library, library)
        self.assertEqual(pending, [])

    def test_portable_reference_checksums(self):
        references = rebuild.read(rebuild.REFS/'routes.json')['entries']
        for row in references:
            if 'recipe_file' in row:
                self.assertEqual(rebuild.digest(rebuild.REFS/row['recipe_file']), row['recipe_sha256'])
                self.assertNotIn('D:/', (rebuild.REFS/row['recipe_file']).read_text(encoding='utf8'))


if __name__ == '__main__':
    unittest.main()
