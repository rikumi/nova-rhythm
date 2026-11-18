"""Read the native disc Canvas camera; rendering pixels are not Canvas units."""
from functools import lru_cache
import hashlib
import math
from pathlib import Path


def focal_length(reference_height, vertical_fov):
    if not math.isfinite(reference_height) or reference_height <= 0 or not 0 < vertical_fov < 180:
        raise ValueError('Invalid Canvas camera calibration')
    return reference_height/(2*math.tan(math.radians(vertical_fov)/2))


def perspective_factor(depth, focal):
    if not math.isfinite(depth) or focal <= 0 or focal+depth <= 0:
        raise ValueError('Native layer lies behind the Canvas camera')
    return focal/(focal+depth)


def camera_for_bundle(bundle):
    directory = Path(bundle).resolve().parent
    candidates = [directory/'ui_disc.unity3d']
    for parent in directory.parents:
        if parent.name in ('Persistent_Store', 'xtlr_Data'):
            game = parent.parent
            candidates = [game/'Persistent_Store/AssetBundles/ui_disc.unity3d',
                          game/'xtlr_Data/StreamingAssets/InstallResource/ui_disc.unity3d']
            break
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        raise FileNotFoundError('The native disc UI camera bundle is required for layer projection')
    return read_camera(str(source), source.stat().st_mtime_ns)


@lru_cache(maxsize=8)
def read_camera(source, _modified):
    import UnityPy
    environment = UnityPy.load(source)
    cameras = {obj.path_id: obj.read_typetree() for obj in environment.objects if obj.type.name == 'Camera'}
    canvases = [obj.read_typetree() for obj in environment.objects if obj.type.name == 'Canvas']
    for canvas in canvases:
        camera = cameras.get(canvas['m_Camera']['m_PathID']) if canvas['m_Camera']['m_FileID'] == 0 else None
        if not camera or canvas['m_RenderMode'] != 1:
            continue
        for obj in environment.objects:
            if obj.type.name != 'MonoBehaviour':
                continue
            try:
                scaler = obj.read_typetree()
            except ValueError:
                continue
            if scaler.get('m_GameObject') != canvas['m_GameObject'] or 'm_ReferenceResolution' not in scaler:
                continue
            if camera['orthographic'] or scaler['m_UiScaleMode'] != 1:
                raise ValueError('Unsupported native disc camera or Canvas scaling mode')
            resolution = scaler['m_ReferenceResolution']
            with Path(source).open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            return {'reference_resolution': [resolution['x'], resolution['y']],
                    'vertical_fov': camera['field of view'],
                    'focal_length': focal_length(resolution['y'], camera['field of view']),
                    'plane_distance': canvas['m_PlaneDistance'], 'source_sha256': digest}
    raise ValueError('No matching camera, Canvas and CanvasScaler found in native disc UI')
