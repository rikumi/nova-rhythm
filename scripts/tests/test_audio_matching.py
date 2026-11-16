from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import numpy as np
    import match_qqmusic as matching
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'Optional analysis dependencies: install requirements.txt to test signal matching')
class AudioMatchingTests(unittest.TestCase):
    def test_fingerprint_candidates_find_shifted_compression_tolerant_copy(self):
        rng = np.random.default_rng(42)
        original = rng.integers(0, 2**32-1, 400, dtype=np.uint32)
        copied = np.concatenate([rng.integers(0, 2**32-1, 23, dtype=np.uint32), original ^ np.uint32(1)])
        qq = {'copy': {'fingerprint': copied}, 'unrelated': {'fingerprint': rng.integers(0, 2**32-1, 500, dtype=np.uint32)}}
        candidates = matching.fingerprint_candidates({'fingerprint': original}, qq, matching.build_index(qq))
        self.assertEqual(candidates[0]['qq_mid'], 'copy')
        self.assertEqual(candidates[0]['offset_frames'], 23)
        self.assertGreater(candidates[0]['fingerprint_similarity'], .95)

    def test_waveform_verification_accepts_gain_and_delay_but_rejects_unrelated_audio(self):
        rate = 11025; rng = np.random.default_rng(1)
        original = rng.normal(0, .05, rate*70)
        copied = np.concatenate([np.zeros(round(rate*.1)), original*.6])
        unrelated = rng.normal(0, .05, rate*71)
        def decode(path, start, length, sample_rate):
            data = original if path == 'local' else copied if path == 'copy' else unrelated
            return data[round(start*rate):round((start+length)*rate)]
        candidate = {'offset_seconds': .1238}
        with patch.object(matching, 'decode', side_effect=decode):
            accepted = matching.waveform_verify(candidate, 'local', 'copy', 70, 70.1)
            rejected = matching.waveform_verify(candidate, 'local', 'unrelated', 70, 71)
        self.assertTrue(accepted['verified'])
        self.assertGreater(accepted['waveform_median'], .99)
        self.assertFalse(rejected['verified'])


if __name__ == '__main__':
    unittest.main()
