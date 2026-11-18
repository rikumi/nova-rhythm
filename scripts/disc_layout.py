"""Native Unity disc geometry shared by research and incremental import."""
import json
import math
import UnityPy
from native_typetrees import component_reader

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

    # The offscreen Canvas uses a perspective camera at 60° FOV and a square
    # 2048 px target. RectTransform z is in Canvas pixels, not CSS pixels.
    # Unity's camera plane distance cancels out when calculating the focal length.
    focal_length = 2048 / (2 * math.tan(math.radians(60) / 2))

    def walk(tid, parent=(0, 0, 1, 1, 0, 0, 1, 2048, 2048, .5, .5), branch='', depth=0):
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
        projection = focal_length / max(focal_length + z, 1)
        q = d['m_LocalRotation']
        angle = parent[4] + math.degrees(math.atan2(2*q['w']*q['z'], 1-2*q['z']**2))
        if name == 'mask' and d.get('m_SizeDelta', {}).get('x', 0):
            result['mask_size'] = d['m_SizeDelta']['x']
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
            })
        for child in d.get('m_Children', []):
            if child['m_PathID'] in transforms:
                walk(child['m_PathID'], (x, y, sx, sy, angle, z, sz, width, height, pivot['x'], pivot['y']), branch, depth + 1)

    walk(by_go[root])
    # Shared sprite assets may legitimately occur at different positions. Only
    # discard an exact duplicate draw, never deduplicate by texture name alone.
    unique = {}
    for layer in result['layers']:
        key = json.dumps({k: layer[k] for k in ['name', 'x', 'y', 'width', 'height', 'pivot', 'rotation', 'opacity']}, sort_keys=True)
        unique.setdefault(key, layer)
    result['layers'] = list(unique.values())
    return result
