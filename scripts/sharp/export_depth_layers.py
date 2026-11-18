"""Plan and package 20 lossless depth slices from the current, corrected metric PLYs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.build/sharp-depth-layers'
VERSION = 1


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(codes=None):
    manifest = read(ROOT/'public/data/sharp-scenes.json')['outfits']
    items = []
    for code in codes or manifest:
        folder = ROOT/'.build/sharp-layering'/code
        scene = read(folder/'scene.json')
        # PLY is the corrected metric scene, including depth and semantic overrides.
        path = folder/'scene.ply'
        if sha(path) != scene['scene_sha256']:
            raise ValueError(f'{code}: stale or damaged PLY')
        with path.open('rb') as stream:
            header = []
            while True:
                line = stream.readline()
                if not line:
                    raise ValueError('Invalid PLY header')
                header.append(line)
                if line == b'end_header\n':
                    break
            expected = ['x','y','z','f_dc_0','f_dc_1','f_dc_2','opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3']
            properties = [line.decode().split()[-1] for line in header if line.startswith(b'property ')]
            if properties != expected:
                raise ValueError('Unsupported PLY layout')
            points = np.fromfile(stream, dtype='<f4').reshape(-1, 14)
        visible = np.isfinite(points).all(axis=1) & (points[:, 2] > 0) & (points[:, 6] > -5.54)
        near, far = map(float, [points[visible, 2].min(), points[visible, 2].max()])
        depths = np.linspace(near, far, 20).tolist()
        fingerprint = hashlib.sha256(json.dumps([VERSION, scene['scene_sha256'], scene['input_size'], depths]).encode()).hexdigest()
        items.append({'code':code, 'version':VERSION, 'fingerprint':fingerprint,
                      'input_size':scene['input_size'], 'depths':depths,
                      'source_scene_sha256':scene['scene_sha256'],
                      'camera_fov_y_degrees':scene['camera_fov_y_degrees'],
                      'focus_distance':scene['focus_distance'], 'depth_percentiles':scene['depth_percentiles']})
    write(RUNTIME/'plan.json', {'items':items})
    print(json.dumps({'prepared':len(items)}))


def linear(rgb):
    rgb = rgb.astype(np.float32)/255
    return np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)


def srgb(rgb):
    return np.where(rgb <= .0031308, rgb*12.92, 1.055*np.maximum(rgb, 0)**(1/2.4)-.055)


def pack(code):
    item = next(item for item in read(RUNTIME/'plan.json')['items'] if item['code']==code)
    folder = RUNTIME/code
    width, height = item['input_size']
    def encode(index):
        path = folder/f'layer-{index:02d}.webp'
        data = np.fromfile(folder/f'{index}.rgba', dtype=np.uint8).reshape(height, width, 4)[::-1].copy()
        # The GL export is straight-alpha sRGB. Preserve both color and alpha losslessly.
        data[data[:,:,3]==0, :3] = 0
        image=Image.fromarray(data)
        box=image.getchannel('A').getbbox()
        if box:
            left,top,right,bottom=box
            box=(max(0,left-1),max(0,top-1),min(width,right+1),min(height,bottom+1))
        else:
            box=(0,0,1,1)
        image.crop(box).save(path, lossless=True, exact=True, method=0)
        return path, data, [box[0],box[1],box[2]-box[0],box[3]-box[1]]
    with ThreadPoolExecutor(max_workers=4) as executor:
        layers = list(executor.map(encode, range(20)))
    composed = np.zeros((height,width,3), dtype=np.float32)
    coverage = np.zeros((height,width,1), dtype=np.float32)
    for _, data, _ in reversed(layers):
        alpha = data[:,:,3:4].astype(np.float32)/255
        composed = linear(data[:,:,:3])*alpha + composed*(1-alpha)
        coverage = alpha + coverage*(1-alpha)
    reference = np.fromfile(folder/'reference.rgba', dtype=np.uint8).reshape(height,width,4)[::-1].copy()
    full = linear(reference[:,:,:3])*(reference[:,:,3:4].astype(np.float32)/255)
    diff = np.abs(srgb(composed)-srgb(full))*255
    item['front_comparison'] = {'mean_absolute_error_255':float(diff.mean()), 'p99_absolute_error_255':float(np.quantile(diff,.99))}
    if not np.isfinite(diff).all() or diff.mean()>1 or np.quantile(diff,.99)>5:
        raise ValueError(f'{code}: layer composition differs from the full Gaussian reference')
    Image.fromarray(np.uint8(np.clip(srgb(composed)*255,0,255))).save(folder/'composite.png')
    Image.fromarray(reference).save(folder/'reference.png')
    entries = []
    offset = 0
    for index, (path, _, rect) in enumerate(layers):
        size = path.stat().st_size
        entries.append({'depth':item['depths'][index], 'offset':offset, 'length':size, 'file':path.name, 'rect':rect})
        offset += size
    header = {**item, 'format':'sharp-depth-layers-v1', 'layers':entries}
    encoded = json.dumps(header, separators=(',',':')).encode()
    package = folder/'scene.layers'
    with package.open('wb') as stream:
        stream.write(b'SDL1'+struct.pack('<I', len(encoded))+encoded)
        for path, _, _ in layers:
            stream.write(path.read_bytes())
    item.update({'layers':entries, 'bytes':package.stat().st_size, 'sha256':sha(package)})
    write(folder/'layers.json', item)
    for path in folder.glob('*.rgba'):
        path.unlink()
    print(json.dumps({'code':code, 'bytes':item['bytes'], **item['front_comparison']}), flush=True)


def recrop():
    """Upgrade earlier full-frame packages without rerendering or changing pixels."""
    for metadata in sorted(RUNTIME.glob('*/layers.json')):
        item=read(metadata)
        if all('rect' in layer for layer in item['layers']):continue
        folder=metadata.parent
        for index in range(20):
            image=np.asarray(Image.open(folder/f'layer-{index:02d}.webp').convert('RGBA'))
            image[::-1].copy().tofile(folder/f'{index}.rgba')
        reference=np.asarray(Image.open(folder/'reference.png').convert('RGBA'))
        reference[::-1].copy().tofile(folder/'reference.rgba')
        pack(item['code'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--codes', nargs='+')
    parser.add_argument('--pack')
    parser.add_argument('--recrop', action='store_true')
    args = parser.parse_args()
    if args.prepare: prepare(args.codes)
    if args.pack: pack(args.pack)
    if args.recrop: recrop()
