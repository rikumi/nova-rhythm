"""Read GyroscopeFollower parameters without modifying game bundles."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import UnityPy

from pipeline_paths import ROOT
manifest_path = ROOT/'public/data/outfits.json'
manifest = json.loads(manifest_path.read_text(encoding='utf8'))


def extract(outfit):
    art = json.loads((ROOT/f'assets/outfit/{outfit["code"]}/manifest.json').read_text(encoding='utf8'))
    env = UnityPy.load(art['source_bundle'])
    gos = {o.path_id: o.read_typetree()['m_Name'] for o in env.objects if o.type.name == 'GameObject'}
    followers = []
    for obj in env.objects:
        if obj.type.name != 'MonoBehaviour':
            continue
        try:
            d = obj.read_typetree()
        except ValueError:
            continue
        if 'fFactorAX' in d:
            followers.append({'node': gos.get(d['m_GameObject']['m_PathID']),
                              **{k: d[k] for k in ['type', 'fFactorX', 'fFactorY', 'fFactorAX', 'fFactorAY']}})
    mask = next((f for f in followers if f['node'] == 'mask'), followers[0] if followers else {})
    motion = {'rotation_x': mask.get('fFactorAX', 3), 'rotation_y': mask.get('fFactorAY', -8)}
    return outfit['code'], {'source': art['source_bundle'], 'followers': followers, 'motion': motion}


with ThreadPoolExecutor(max_workers=2) as pool:
    rows = dict(pool.map(extract, manifest['items']))
for outfit in manifest['items']:
    outfit['card']['motion'] = rows[outfit['code']]['motion']
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
(ROOT/'data/card_motion.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')
print('Read native motion:', len(rows), 'outfits')
