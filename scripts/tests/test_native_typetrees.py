import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

AVAILABLE = importlib.util.find_spec('UnityPy') is not None
if AVAILABLE:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from native_typetrees import TypeTreeCache


def component(script=b'image-script', schema=b'image-schema', node=None):
    obj = SimpleNamespace(serialized_type=SimpleNamespace(
        class_id=114, script_id=script, old_type_hash=schema, node=node))

    def read_typetree(nodes=None, check_read=True):
        if nodes is None and obj.serialized_type.node is None:
            raise ValueError('Expected to read 136 bytes, but only read 32 bytes')
        if not check_read:
            raise AssertionError('Full payload validation must remain enabled')
        return {'m_Sprite': {'m_PathID': 123}, 'm_Enabled': 1}

    obj.read_typetree = read_typetree
    return obj


@unittest.skipUnless(AVAILABLE, 'Optional UnityPy analysis dependency is unavailable')
class NativeTypeTreeTests(unittest.TestCase):
    def test_identical_donor_schema_restores_stripped_sprite_reference(self):
        cache = TypeTreeCache(['donor.unity3d'])
        donor = SimpleNamespace(objects=[component(node=object())])
        with patch('native_typetrees.UnityPy.load', return_value=donor):
            self.assertEqual(cache.read(component())['m_Sprite']['m_PathID'], 123)
        # The recovered schema can be reused after the donor iterator is exhausted.
        self.assertEqual(cache.read(component())['m_Enabled'], 1)

    def test_same_script_with_different_schema_or_different_script_is_rejected(self):
        for mismatch in [component(schema=b'older-layout'), component(script=b'another-script')]:
            cache = TypeTreeCache([])
            cache.register(SimpleNamespace(objects=[component(node=object())]), 'donor')
            with self.assertRaisesRegex(ValueError, '136 bytes'):
                cache.read(mismatch)

    def test_existing_type_tree_needs_no_donor_access(self):
        cache = TypeTreeCache(['must-not-load.unity3d'])
        with patch('native_typetrees.UnityPy.load', side_effect=AssertionError('Unexpected donor read')):
            self.assertEqual(cache.read(component(node=object()))['m_Enabled'], 1)


if __name__ == '__main__':
    unittest.main()
