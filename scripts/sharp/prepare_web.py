"""Prepare runtime URLs from the verified site-assets branch, without bundling binaries."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]


def prepare(asset_base=None):
    assets=json.loads((ROOT/'references/runtime-assets.json').read_text(encoding='utf8'))
    asset_base=asset_base or assets['raw_base']+'/models'
    parsed=urlparse(asset_base)
    if parsed.scheme!='https' or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('asset-base must be an HTTPS download directory without query or fragment')
    results=json.loads((ROOT/'references/sharp-scenes-results.json').read_text(encoding='utf8'))
    if not results['publication'].get('verified'):raise ValueError('Source scenes must pass verification first')
    keys=['input_size','camera_fov_y_degrees','focus_distance','depth_percentiles','gaussian_count',
          'scene_format','scene_sha256','compressed_sha256','compressed_bytes','name']
    outfits={code:{**{key:scene[key] for key in keys},
        'scene_url':asset_base.rstrip('/')+'/'+scene['scene_url'].rsplit('/',1)[-1]}
        for code,scene in results['outfits'].items()}
    layer_results=ROOT/'references/sharp-depth-layers-results.json'
    if layer_results.exists():
        layers=json.loads(layer_results.read_text(encoding='utf8'))
        if not layers['publication'].get('verified'):raise ValueError('Depth layers must pass publication verification')
        for code,scene in layers['outfits'].items():
            if code in outfits and scene['source_scene_sha256']==outfits[code]['scene_sha256']:
                outfits[code]['layer_scene']={'url':assets['raw_base']+'/'+scene['path'],'bytes':scene['bytes'],'sha256':scene['sha256'],'layer_count':20}
    manifest={'schemaVersion':1,'asset_commit':assets['commit'],'outfits':outfits}
    target=ROOT/'public/data/sharp-scenes.json'
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    catalog_path=ROOT/'public/data/outfits.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf8'))
    for outfit in catalog['items']:
        outfit['staticImage']=assets['raw_base']+'/artwork/'+outfit['code']+'.png'
    catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(f'Prepared {len(outfits)} scene entries at {target.relative_to(ROOT)}; no binary assets copied')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--asset-base')
    prepare(parser.parse_args().asset_base)
