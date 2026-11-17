import importlib.util
import sys
import unittest
from pathlib import Path

AVAILABLE=all(importlib.util.find_spec(name) for name in ['numpy','scipy'])
if AVAILABLE:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sharp'))
    from export_scene import metric_gaussians,semantic_warp


@unittest.skipUnless(AVAILABLE,'Optional local SHARP analysis dependencies are unavailable')
class SharpGeometryTests(unittest.TestCase):
    def test_semantic_depth_moves_subject_behind_water_without_changing_screen_footprint(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        positions=np.array([[.2,.1,1.],[.2,.1,1.],[.1,-.1,1.1]])
        scales=np.full((3,3),.02);q=np.tile([1.,0,0,0],(3,1))
        weights=np.array([1.,0.,.5])
        gradient=np.array([[0.,0,0],[0.,0,0],[.6,-.3,-.09/1.1]])
        settings=dict(foreground_depth=1.25,background_depth=.85,foreground_detail_scale=.35,background_detail_scale=.75)
        moved,sizes,rotation=semantic_warp(positions,scales,q,weights,gradient,1.,settings)
        self.assertGreater(moved[0,2],moved[1,2])
        np.testing.assert_allclose(moved[:,:2]/moved[:,2,None],positions[:,:2]/positions[:,2,None])
        for old,new,size,quat in zip(positions,moved,sizes,rotation):
            def projection(p):
                x,y,z=p;return np.array([[1/z,0,-x/z**2],[0,1/z,-y/z**2]])
            before=projection(old)@np.diag([.02]*3)
            after=projection(new)@(Rotation.from_quat(quat[[1,2,3,0]]).as_matrix()*size[None,:])
            np.testing.assert_allclose(after@after.T,before@before.T,atol=1e-13)

    def test_inverse_depth_compression_preserves_original_screen_footprint(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        means=np.array([[.1,.2,2],[2.,1.,100],[3.,2.,300.]])
        scales=np.full((3,3),.02);q=np.tile([1.,0,0,0],(3,1));axes=np.array([.5,.5,1.])
        original=means*axes;factor=.02;focus=125.
        positions,converted,rot=metric_gaussians(means,scales,q,axes,factor,focus)
        np.testing.assert_allclose(positions[:,:2]/positions[:,2,None],original[:,:2]/original[:,2,None])
        np.testing.assert_allclose(1/positions[:,2],1/focus+factor*(1/original[:,2]-1/focus))
        for i in range(3):
            def projection(point):
                x,y,z=point;return np.array([[1/z,0,-x/z**2],[0,1/z,-y/z**2]])
            old_basis=np.diag(scales[i]*axes)
            new_basis=Rotation.from_quat(rot[i,[1,2,3,0]]).as_matrix()*converted[i][None,:]
            old_projected=projection(original[i])@old_basis
            new_projected=projection(positions[i])@new_basis
            np.testing.assert_allclose(new_projected@new_projected.T,old_projected@old_projected.T,atol=1e-13)

    def test_unprojection_preserves_pinhole_projection_and_oriented_covariance(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        random=np.random.default_rng(17)
        means=random.normal(size=(40,3));means[:,2]=random.uniform(1,4,40)
        scales=random.uniform(.001,.1,(40,3))
        quaternions=random.normal(size=(40,4));quaternions/=np.linalg.norm(quaternions,axis=1,keepdims=True)
        axes=np.array([2400/(2*2039),1700/(2*2039),1])
        xyz,converted,q=metric_gaussians(means,scales,quaternions,axes)
        np.testing.assert_allclose(xyz[:,0]*2039/xyz[:,2],means[:,0]*1200/means[:,2])
        np.testing.assert_allclose(xyz[:,1]*2039/xyz[:,2],means[:,1]*850/means[:,2])
        old_rotation=Rotation.from_quat(quaternions[:,[1,2,3,0]]).as_matrix()
        old_basis=old_rotation*scales[:,None,:]*axes[None,:,None]
        expected=old_basis@old_basis.transpose(0,2,1)
        rotation=Rotation.from_quat(q[:,[1,2,3,0]]).as_matrix()
        new_basis=rotation*converted[:,None,:]
        np.testing.assert_allclose(new_basis@new_basis.transpose(0,2,1),expected,atol=1e-12)
        np.testing.assert_allclose(np.linalg.det(rotation),1,atol=1e-12)


if __name__=='__main__':unittest.main()
