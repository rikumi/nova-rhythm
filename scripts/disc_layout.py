"""Native Unity disc geometry shared by research and incremental import."""
import json
import math
import UnityPy
import numpy as np
from native_typetrees import component_reader
from disc_camera import camera_for_bundle, perspective_factor
from disc_mesh import mesh_bounds

def layout(item, diagnostics=None, sprite_exports=None):
    art = item['artwork']
    code = item['code']
    result = {'mask_size': 712, 'layers': [], 'motion': {'rotation_x': 3, 'rotation_y': -8}}
    e = UnityPy.load(art['source_bundle'])
    read_component = component_reader(art['source_bundle'], e)
    objects = {o.path_id: o for o in e.objects}
    gos = {o.path_id: o.read_typetree() for o in e.objects if o.type.name == 'GameObject'}
    transforms = {o.path_id: o.read_typetree() for o in e.objects if o.type.name in ['RectTransform', 'Transform']}
    by_go = {d['m_GameObject']['m_PathID']: tid for tid, d in transforms.items()}
    root = next((ptr.path_id for path, ptr in e.container.items() if path.endswith(code + '_g.prefab')), None)
    if root is None or root not in by_go:
        return result

    # RectTransform z is in reference Canvas units. RenderTexture resolution
    # changes raster density and must not change the apparent size of the artwork.
    camera = camera_for_bundle(art['source_bundle'])
    result['camera'] = camera
    focal_length = camera['focal_length']

    def walk(tid, parent=(0, 0, 1, 1, 0, 0, 1, *camera['reference_resolution'], .5, .5), branch='', depth=0, matrix=None):
        d = transforms[tid]
        go = gos[d['m_GameObject']['m_PathID']]
        if not go.get('m_IsActive', 1):
            return
        name = go['m_Name']
        if name.startswith('layer_'):
            branch = name
        local_pos = d.get('m_LocalPosition', {'x': 0, 'y': 0, 'z': 0})
        pos = d.get('m_AnchoredPosition', local_pos)
        scale = d['m_LocalScale']
        amin = d.get('m_AnchorMin', {'x': .5, 'y': .5})
        amax = d.get('m_AnchorMax', {'x': .5, 'y': .5})
        pivot = d.get('m_Pivot', {'x': .5, 'y': .5})
        size = d.get('m_SizeDelta', {'x': 0, 'y': 0})
        width = size['x'] + parent[7] * (amax['x'] - amin['x'])
        height = size['y'] + parent[8] * (amax['y'] - amin['y'])
        anchor_x = parent[7] * (amin['x'] + (amax['x'] - amin['x']) * pivot['x'] - parent[9])
        anchor_y = parent[8] * (amin['y'] + (amax['y'] - amin['y']) * pivot['y'] - parent[10])
        x, y = parent[0] + (pos['x'] + anchor_x) * parent[2], parent[1] + (pos['y'] + anchor_y) * parent[3]
        sx, sy = parent[2] * scale['x'], parent[3] * scale['y']
        z = parent[5] + local_pos.get('z', 0) * parent[6]
        sz = parent[6] * scale['z']
        projection = perspective_factor(z, focal_length)
        q = d['m_LocalRotation']
        angle = parent[4] + math.degrees(math.atan2(2*q['w']*q['z'], 1-2*q['z']**2))
        if name == 'mask' and d.get('m_SizeDelta', {}).get('x', 0):
            result['mask_size'] = d['m_SizeDelta']['x']
        components = []
        additive = False
        follower = False
        for comp in go.get('m_Component', []):
            o = objects.get(comp['component']['m_PathID'])
            if not o or o.type.name != 'MonoBehaviour':
                continue
            try:
                b = read_component(o)
            except ValueError as exc:
                if diagnostics is not None:
                    diagnostics.append({'code': code, 'node': name, 'branch': branch,
                                        'component': o.path_id, 'error': str(exc)})
                continue
            components.append(b)
            script_ref = b.get('m_Script', {})
            script = objects.get(script_ref.get('m_PathID')) if script_ref.get('m_FileID') == 0 else None
            if b.get('m_Enabled', 1) and script and script.type.name == 'MonoScript':
                metadata = script.read()
                follower |= metadata.m_ClassName == 'GyroscopeFollower'
                if metadata.m_ClassName == 'UIAdditiveEffect' and metadata.m_Namespace == 'UnityEngine.UI.Extensions':
                    additive = True
        # Followers overwrite the prefab's saved preview tilt at runtime.
        # Keep static transforms (notably a floor rotated 90 degrees) intact.
        qx, qy, qz, qw = (0, 0, 0, 1) if follower else (q['x'], q['y'], q['z'], q['w'])
        rotation = np.array([[1-2*(qy*qy+qz*qz), 2*(qx*qy-qz*qw), 2*(qx*qz+qy*qw)],
                             [2*(qx*qy+qz*qw), 1-2*(qx*qx+qz*qz), 2*(qy*qz-qx*qw)],
                             [2*(qx*qz-qy*qw), 2*(qy*qz+qx*qw), 1-2*(qx*qx+qy*qy)]])
        local_matrix = np.eye(4)
        local_matrix[:3, :3] = rotation @ np.diag([scale['x'], scale['y'], scale['z']])
        local_matrix[:3, 3] = [pos['x']+anchor_x, pos['y']+anchor_y, local_pos.get('z', 0)]
        world_matrix = (np.eye(4) if matrix is None else matrix) @ local_matrix
        # Effect components may follow the Image component in the prefab.
        for b in components:
            if name == 'mask' and 'fFactorAX' in b:
                result['motion'] = {'rotation_x': b['fFactorAX'], 'rotation_y': b['fFactorAY']}
            if 'm_Sprite' not in b or not b.get('m_Enabled', 1):
                continue
            reference = b['m_Sprite']
            # Shared UI mask/frame sprites are external to this disc bundle.
            if reference['m_FileID'] != 0:
                continue
            sprite = objects.get(reference['m_PathID'])
            if not sprite or sprite.type.name != 'Sprite':
                continue
            sprite_name = sprite.read().m_Name
            if branch == 'layer_-1':
                continue
            if sprite_exports is not None:
                sprite_exports[sprite_name] = sprite
            size = d.get('m_SizeDelta', {})
            result['layers'].append({
                'name': sprite_name, 'path': f'/art/{code}/{sprite_name}.webp',
                'x': round(x * projection, 4), 'y': round(y * projection, 4),
                'width': round(abs(width * sx * projection), 4),
                'height': round(abs(height * sy * projection), 4),
                'native_z': round(z, 4), 'projection_factor': round(projection, 6),
                'pivot': d.get('m_Pivot', {'x': .5, 'y': .5}),
                'rotation': round(angle, 4), 'branch': branch,
                'opacity': b.get('m_Color', {}).get('a', 1),
                'is_title': branch == 'layer_title',
                **({'blend_mode': 'additive', 'blend_source': 'UnityEngine.UI.Extensions.UIAdditiveEffect'} if additive else {}),
            })
            if 'm_warpManager' in b and (abs(qx) > .5 or abs(qy) > .5):
                mesh = {'corners': [], 'subdivisions': b['m_numSubdivisions'], 'focal_length': focal_length}
                for corner in ('BL', 'TL', 'TR', 'BR'):
                    p = b['m_warpManager']['m_cornerPosition'+corner]
                    mesh['corners'].append((world_matrix @ [p['x'], p['y'], p['z'], 1])[:3].tolist())
                layer = result['layers'][-1]
                layer.update(mesh_bounds(mesh, focal_length))
                layer['native_mesh'] = mesh
                layer['path'] = f'/art/{code}/{sprite_name}_native-mesh.webp'
        for child in d.get('m_Children', []):
            if child['m_PathID'] in transforms:
                walk(child['m_PathID'], (x, y, sx, sy, angle, z, sz, width, height, pivot['x'], pivot['y']), branch, depth + 1, world_matrix)

    walk(by_go[root])
    # Shared sprite assets may legitimately occur at different positions. Only
    # discard an exact duplicate draw, never deduplicate by texture name alone.
    unique = {}
    for layer in result['layers']:
        key = json.dumps({**{k: layer[k] for k in ['name', 'x', 'y', 'width', 'height', 'pivot', 'rotation', 'opacity']},
                          'blend_mode': layer.get('blend_mode', 'normal')}, sort_keys=True)
        unique.setdefault(key, layer)
    result['layers'] = list(unique.values())
    return result
