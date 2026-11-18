import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from disc_camera import focal_length, perspective_factor


class DiscCameraTests(unittest.TestCase):
    def test_render_target_density_does_not_change_canvas_projection(self):
        focal = focal_length(1080, 60)
        pixels_per_unit = 2048/1080
        for depth in [-200, 0, 1200, 3350]:
            self.assertAlmostEqual(perspective_factor(depth, focal),
                                   perspective_factor(depth*pixels_per_unit, focal_length(2048, 60)))
        self.assertNotAlmostEqual(perspective_factor(3350, focal),
                                  perspective_factor(3350, focal_length(2048, 60)))

    def test_far_backgrounds_shrink_more_and_near_titles_enlarge_more(self):
        focal = focal_length(1080, 60)
        self.assertAlmostEqual(focal, 935.3074360871938)
        self.assertAlmostEqual(perspective_factor(0, focal), 1)
        self.assertLess(perspective_factor(3350, focal), .22)
        self.assertGreater(perspective_factor(-200, focal), 1.27)

    def test_invalid_calibration_and_behind_camera_planes_are_rejected(self):
        for height, fov in [(0, 60), (math.inf, 60), (1080, 0), (1080, 180)]:
            with self.assertRaises(ValueError):
                focal_length(height, fov)
        with self.assertRaises(ValueError):
            perspective_factor(-1000, focal_length(1080, 60))
