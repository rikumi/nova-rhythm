import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'layering'))
from run_batch import apply_layer_order, review_for_result
from publish_layers import approved_batch
from types import SimpleNamespace


class LayerReviewTests(unittest.TestCase):
    def setUp(self):
        self.result = {'layers': [{'file': name, 'sha256': name + '-hash'}
                                  for name in ['background', 'deer', 'person']]}

    def test_reorder_preserves_layer_content_and_ignores_stale_hashes(self):
        order = ['background', 'person', 'deer']
        hashes = {layer['file']: layer['sha256'] for layer in self.result['layers']}
        item = {'layer_order': order, 'layer_order_hashes': hashes}
        reordered = apply_layer_order(self.result, item)
        self.assertEqual([layer['file'] for layer in reordered['layers']], order)
        self.assertEqual({layer['file']: layer['sha256'] for layer in reordered['layers']}, hashes)
        restored = apply_layer_order(reordered, {**item, 'layer_order_hashes': {'deer': 'old-hash'}})
        self.assertEqual(restored['layers'], self.result['layers'])

    def test_regeneration_invalidates_acceptance_but_reorder_does_not(self):
        review = {'status': 'accepted', 'layer_hashes': {
            layer['file']: layer['sha256'] for layer in self.result['layers']}}
        self.assertEqual(review_for_result(self.result, review)['status'], 'accepted')
        self.assertEqual(review_for_result({'layers': self.result['layers'][::-1]}, review)['status'], 'accepted')
        changed = {'layers': [*self.result['layers'][:-1], {'file': 'person', 'sha256': 'new'}]}
        self.assertEqual(review_for_result(changed, review)['status'], 'needs_review')

    def test_reviewed_publication_excludes_revoked_and_changed_artwork(self):
        hashes = {layer['file']: layer['sha256'] for layer in self.result['layers']}
        batch = SimpleNamespace(batch=Path('.'), runtime=Path('.'),
            completed={code: self.result for code in ['passed', 'revoked', 'changed']},
            plan={'items': [{'code': code} for code in ['passed', 'revoked', 'changed']]})
        reviews = {'passed': {'status': 'accepted', 'layer_hashes': hashes},
                   'revoked': {'status': 'revision_requested', 'layer_hashes': hashes},
                   'changed': {'status': 'accepted', 'layer_hashes': {'old': 'old-hash'}}}
        selected = approved_batch(batch, reviews)
        self.assertEqual(list(selected.completed), ['passed'])
        self.assertEqual(selected.plan['items'], [{'code': 'passed'}])
        self.assertEqual(len(batch.completed), 3)


if __name__ == '__main__':
    unittest.main()
