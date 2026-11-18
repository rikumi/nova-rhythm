from pathlib import Path
import sys
import unittest
import importlib.util

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
AVAILABLE = all(importlib.util.find_spec(module) for module in ('numpy', 'PIL'))
if AVAILABLE:
    import numpy as np
    from PIL import Image
    from disc_mesh import layer_image, mesh_bounds, mesh_vertices


class Sprite:
    def __init__(self, image):
        self.image = image

    def read(self):
        return self


@unittest.skipUnless(AVAILABLE, 'Native mesh extraction requires local image-analysis dependencies')
class DiscMeshTests(unittest.TestCase):
    def test_flat_mesh_preserves_texture_orientation_and_alpha(self):
        image = Image.new('RGBA', (8, 8), (0, 0, 0, 0))
        image.paste((240, 50, 20, 255), (0, 0, 4, 4))
        mesh = {'corners': [[-4, -4, 0], [-4, 4, 0], [4, 4, 0], [4, -4, 0]],
                'subdivisions': 2, 'focal_length': 100}
        layer = {**mesh_bounds(mesh, 100), 'native_mesh': mesh}
        pixels = np.asarray(layer_image(layer, Sprite(image)))
        self.assertEqual(pixels.shape, (16, 16, 4))
        self.assertTrue(np.array_equal(pixels[2, 2], [240, 50, 20, 255]))
        self.assertEqual(pixels[13, 13, 3], 0)
        self.assertTrue(np.all(pixels[:6, :6, 3] == 255))  # no triangle seams

    def test_perspective_uses_each_vertex_depth_and_subdivides_the_surface(self):
        mesh = {'corners': [[-10, -10, 0], [-10, 10, 100],
                            [10, 10, 100], [10, -10, 0]], 'subdivisions': 2}
        uv, points = mesh_vertices(mesh, 100)
        np.testing.assert_allclose(points[0], [-5, 5])
        np.testing.assert_allclose(points[-1], [10, -10])
        np.testing.assert_allclose(points[3], [-10/1.5, 0])
        self.assertEqual(len(uv), 9)

    def test_camera_crossing_is_rejected(self):
        mesh = {'corners': [[0, 0, -101]]*4, 'subdivisions': 1}
        with self.assertRaises(ValueError):
            mesh_vertices(mesh, 100)
