"""Reproducible layer transfers using existing pixels only; never runs inference."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

from run_batch import ROOT, read, write, digest


def apply(runtime, code, correction):
    import numpy as np
    from PIL import Image
    folder = runtime / code
    path = folder / 'result.json'
    result = read(path)
    fingerprint = hashlib.sha256(json.dumps(correction, sort_keys=True).encode()).hexdigest()
    if result.get('postprocessing', {}).get('fingerprint') == fingerprint:
        return result
    backup = folder / 'before-review-correction'
    if backup.exists():
        raise RuntimeError(f'{code}: existing backup requires explicit review before another correction')
    backup.mkdir()
    for entry in result['layers']:
        source = folder / entry['file']
        if digest(source) != entry['sha256']:
            raise RuntimeError(f'{code}: source hash mismatch: {source}')
        shutil.copy2(source, backup / source.name)
    shutil.copy2(path, backup / path.name)
    images = {entry['file']: Image.open(folder / entry['file']).convert('RGBA') for entry in result['layers']}

    def composite():
        canvas = Image.new('RGBA', result['input_size'])
        for entry in result['layers']:
            canvas.alpha_composite(images[entry['file']])
        return canvas

    before = composite()
    for operation in correction['operations']:
        source, target = operation['source'], operation['target']
        piece = Image.new('RGBA', images[source].size)
        if operation.get('rect'):
            box = tuple(operation['rect'])
            piece.paste(images[source].crop(box), box[:2])
            images[source].paste((0, 0, 0, 0), box)
        else:
            piece = images[source].copy()
            images[source] = Image.new('RGBA', piece.size)
        images[target] = Image.alpha_composite(piece, images[target]) if operation['placement'] == 'behind' else Image.alpha_composite(images[target], piece)
    after = composite()
    delta = np.abs(np.asarray(before).astype(int) - np.asarray(after).astype(int))
    # Compare visible output, ignoring hidden RGB in fully transparent pixels.
    visible = (np.asarray(before)[:, :, 3] > 0) | (np.asarray(after)[:, :, 3] > 0)
    maximum = int(delta[visible].max())
    mean = float(delta[visible].mean())
    if maximum > 3 or mean > .05:
        raise RuntimeError(f'{code}: transfer changes the composition (max={maximum}, mean={mean}); originals retained')
    result = copy.deepcopy(result)
    entries = []
    for entry in result['layers']:
        image = images[entry['file']]
        if image.getchannel('A').getextrema()[1] == 0:
            continue
        image.save(folder / entry['file'])
        entry.update(sha256=digest(folder / entry['file']), visible_fraction=round(float((np.asarray(image)[:, :, 3] > 8).mean()), 6))
        entries.append(entry)
    result['layers'] = entries
    result['postprocessing'] = {'fingerprint': fingerprint, 'correction': correction, 'composite_max_error': maximum, 'composite_mean_error': mean}
    after.save(folder / 'reconstructed.png')
    write(path, result)
    print(f'{code}: {len(entries)} layers, composite max error {maximum}, mean {mean:.6f}')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, default=ROOT / '.build/layering-trial')
    parser.add_argument('--code')
    args = parser.parse_args()
    corrections = read(ROOT / 'references/experimental-layering-corrections.json')['items']
    for code, correction in corrections.items():
        if correction['action'] == 'postprocess' and (not args.code or args.code == code):
            apply(args.runtime, code, correction)


if __name__ == '__main__':
    main()
