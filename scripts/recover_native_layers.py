"""Audit and repair every native layout from read-only local game bundles."""
import concurrent.futures
import hashlib
import json
from pathlib import Path

from PIL import Image

from disc_layout import layout

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save_layer(job):
    image, target = job
    target.parent.mkdir(parents=True, exist_ok=True)
    image.convert('RGBA').save(target, 'WEBP', lossless=True, method=4, exact=True)
    return {'path': target.relative_to(ROOT).as_posix(), 'sha256': digest(target)}


def main():
    catalog_path = ROOT/'public/data/outfits.json'
    catalog = read(catalog_path)
    recovered = {}
    jobs = {}
    diagnostics = []
    audited = {}
    for outfit in catalog['items']:
        code = outfit['code']
        art_path = ROOT/f'assets/outfit/{code}/manifest.json'
        if not art_path.exists():
            continue
        art = read(art_path)
        sprites = {}
        card = layout({'code': code, 'artwork': art}, diagnostics, sprites)
        audited[code] = {'source_sha256': art['source_sha256'], 'layer_count': len(card['layers'])}
        if not card['layers']:
            continue
        changed = card != outfit['card']
        missing = False
        for layer in card['layers']:
            target = ROOT/'public'/layer['path'].lstrip('/')
            if not target.exists() and target not in jobs:
                # Follow the exact Sprite reference, including unprefixed and packed textures.
                jobs[target] = (sprites[layer['name']].read().image, target)
                missing = True
        if not changed and not missing:
            continue
        recovered[code] = {'name': outfit['name'], 'source_sha256': art['source_sha256'],
                           'basis': 'Original _G prefab and referenced Sprites; exact script_id and old_type_hash schema matching',
                           'card': card}
        outfit['card'] = card
        print(f'{code}: {len(card["layers"])} native layers recovered', flush=True)
    if diagnostics:
        raise ValueError(f'Native layout audit found {len(diagnostics)} unreadable components: {diagnostics}')
    # Write the catalog only after every texture is exported successfully.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        textures = list(pool.map(save_layer, jobs.values()))
    report_path = ROOT/'references/native-layer-recovery.json'
    report = read(report_path) if report_path.exists() else {'schemaVersion': 1, 'outfits': {}, 'textures': []}
    report['outfits'].update(recovered)
    report['audit'] = {'outfits': audited, 'unreadable_components': diagnostics,
                       'native_count': sum(row['layer_count'] > 0 for row in audited.values())}
    report['textures'] = list({row['path']: row for row in [*report['textures'], *textures]}.values())
    write(report_path, report)
    if recovered:
        write(catalog_path, catalog)
    print(f'Restored {len(recovered)} outfits and {len(textures)} full-resolution lossless native textures')


if __name__ == '__main__':
    main()
