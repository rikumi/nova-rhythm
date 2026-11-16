"""Export the game's actual home Story/Recruit icon hierarchies as SVG images."""
from pathlib import Path
import base64
import io
import json
import math
import UnityPy
from PIL import Image

from pipeline_paths import ROOT
from pipeline_paths import GAME
VERSION = GAME/'Persistent_Store/AssetBundles'
env = UnityPy.load(str(VERSION/'ui_mainviewex.unity3d'))
objects = {o.path_id: o for o in env.objects}
gos = {o.path_id: o.read_typetree() for o in env.objects if o.type.name == 'GameObject'}
transforms = {o.path_id: o.read_typetree() for o in env.objects if o.type.name == 'RectTransform'}
by_go = {v['m_GameObject']['m_PathID']: k for k, v in transforms.items()}


def path(tid):
    parts = []
    while tid in transforms:
        t = transforms[tid]; parts.append(gos[t['m_GameObject']['m_PathID']]['m_Name']); tid = t['m_Father']['m_PathID']
    return '/'.join(reversed(parts))


icons = {}
for category, button in [('story', 'btnMainline'), ('system', 'btnRecruit')]:
    root = next(tid for tid in transforms if path(tid).endswith(f'/{button}/AnimRoot/RootSD'))
    layers = []

    def walk(tid, parent=(0, 0, 1, 1, 0, 0, .5, .5, 0), root_node=False):
        t = transforms[tid]; go = gos[t['m_GameObject']['m_PathID']]
        if not go.get('m_IsActive', True):
            return
        amin, amax, pivot = t['m_AnchorMin'], t['m_AnchorMax'], t['m_Pivot']
        size, pos, scale = t['m_SizeDelta'], t['m_AnchoredPosition'], t['m_LocalScale']
        w = size['x'] + parent[4] * (amax['x'] - amin['x'])
        h = size['y'] + parent[5] * (amax['y'] - amin['y'])
        dx = (pos['x'] + parent[4] * (amin['x'] + (amax['x'] - amin['x']) * pivot['x'] - parent[6])) * parent[2]
        dy = (pos['y'] + parent[5] * (amin['y'] + (amax['y'] - amin['y']) * pivot['y'] - parent[7])) * parent[3]
        a = math.radians(parent[8])
        x = parent[0] + dx * math.cos(a) - dy * math.sin(a)
        y = parent[1] + dx * math.sin(a) + dy * math.cos(a)
        q = t['m_LocalRotation']; angle = parent[8] + math.degrees(math.atan2(2*q['w']*q['z'], 1-2*q['z']**2))
        sx, sy = parent[2] * scale['x'], parent[3] * scale['y']
        if root_node:
            x = y = angle = 0
        for component in go['m_Component']:
            obj = objects.get(component['component']['m_PathID'])
            if not obj or obj.type.name != 'MonoBehaviour':
                continue
            d = obj.read_typetree(); sprite_id = d.get('m_Sprite', {}).get('m_PathID')
            alpha = d.get('m_Color', {}).get('a', 1)
            if sprite_id and d.get('m_Enabled', 1) and alpha > 0:
                layers.append({'node': path(tid), 'sprite_id': sprite_id, 'x': x, 'y': -y,
                               'width': abs(w*sx), 'height': abs(h*sy), 'pivot': pivot,
                               'rotation': -angle, 'scale_x': -1 if sx < 0 else 1,
                               'scale_y': -1 if sy < 0 else 1, 'opacity': alpha})
        for child in t['m_Children']:
            if child['m_PathID'] in transforms:
                walk(child['m_PathID'], (x, y, sx, sy, w, h, pivot['x'], pivot['y'], angle))

    walk(root, root_node=True)
    icons[category] = {'source': str(VERSION/'ui_mainviewex.unity3d'), 'root': path(root), 'layers': layers}

wanted = {l['sprite_id'] for icon in icons.values() for l in icon['layers']}
sprites = {}; files = {}
for directory in [GAME/'xtlr_Data/StreamingAssets/InstallResource', VERSION]:
    for p in directory.glob('*.unity3d'):
        if p.name.startswith(('icon-', 'image-', 'ui_common', 'ui_mainview', 'ui_big_sprites')):
            files[p.name] = p
for p in files.values():
    e = UnityPy.load(str(p))
    for o in e.objects:
        if o.type.name != 'Sprite' or o.path_id not in wanted:
            continue
        s = o.read(); image = s.image
        full = Image.new('RGBA', (round(s.m_Rect.width), round(s.m_Rect.height)))
        offset = s.m_RD.textureRectOffset
        full.paste(image, (round(offset.x), full.height - round(offset.y) - image.height))
        stream = io.BytesIO(); full.save(stream, format='PNG')
        sprites[o.path_id] = {'name': s.m_Name, 'source': str(p), 'width': full.width, 'height': full.height,
                              'uri': 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode('ascii')}
missing = wanted - sprites.keys()
if missing:
    raise ValueError('Missing home sprites: ' + str(missing))
for category, icon in icons.items():
    parts = []; corners = []
    for layer in icon['layers']:
        sprite = sprites[layer['sprite_id']]
        layer.update({'name': sprite['name'], 'source': sprite['source'],
                      'source_width': sprite['width'], 'source_height': sprite['height']})
        w, h = layer['width'] or sprite['width'], layer['height'] or sprite['height']
        x0, y0 = -layer['pivot']['x'] * w, -(1-layer['pivot']['y']) * h
        angle = math.radians(layer['rotation']); c, s = math.cos(angle), math.sin(angle)
        for x, y in [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]:
            x *= layer['scale_x']; y *= layer['scale_y']
            corners.append((layer['x'] + x*c - y*s, layer['y'] + x*s + y*c))
        parts.append(f'<g transform="translate({layer["x"]} {layer["y"]}) rotate({layer["rotation"]}) scale({layer["scale_x"]} {layer["scale_y"]})" opacity="{layer["opacity"]}"><image x="{x0}" y="{y0}" width="{w}" height="{h}" href="{sprite["uri"]}"/></g>')
    x0 = min(x for x, y in corners)-2; y0 = min(y for x, y in corners)-2
    w = max(x for x, y in corners)-x0+2; h = max(y for x, y in corners)-y0+2
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{x0} {y0} {w} {h}">' + ''.join(parts) + '</svg>'
    (ROOT/f'public/ui/home-native-{category}.svg').write_text(svg, encoding='utf8')
    print(category, len(icon['layers']), 'native layers', round(w), round(h))
(ROOT/'data/home_native_icons.json').write_text(json.dumps(icons, ensure_ascii=False, indent=2), encoding='utf8')
