"""Compare installed disc patches and export only textures used by the website.

Game directories are read-only. No client configuration or game download is run.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

from pipeline_paths import GAME, REPOSITORY, protect_output


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pixel_digest(image):
    return hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()


def textures(bundle, names):
    import UnityPy
    result = {}
    for obj in UnityPy.load(str(bundle)).objects:
        if obj.type.name == 'Texture2D':
            texture = obj.read()
            if texture.m_Name in names:
                result[texture.m_Name] = texture.image.convert('RGBA')
    return result


def image_bytes(image, kind, **options):
    stream = io.BytesIO()
    image.save(stream, kind, **options)
    return stream.getvalue()


def save_changed(target, content):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_bytes() != content:
        target.write_bytes(content)


def asset_path(output, path):
    if not path.startswith('/') or path.startswith('//'):
        raise ValueError(f'Expected a local website asset: {path}')
    target = (output / path.lstrip('/')).resolve()
    if not target.is_relative_to(output.resolve()):
        raise ValueError(f'Asset escapes output: {path}')
    return target


def apply_patches(outfits, game, output, originals=None, apply=False):
    from PIL import Image
    from export_share_previews import save_preview

    output = protect_output(output, game)
    if originals is not None:
        originals = protect_output(originals, game)
    report = {'schema_version': 1, 'source': 'Patch_Store/AssetBundles',
              'comparison': 'Decoded RGBA pixels against Persistent_Store, falling back to InstallResource',
              'applied': apply, 'items': [], 'errors': []}
    for outfit in outfits['items']:
        code = outfit['code']
        patch = game / f'Patch_Store/AssetBundles/disc_{code}.unity3d'
        if not patch.is_file():
            continue
        base = next((path for path in [game / f'Persistent_Store/AssetBundles/{patch.name}',
                    game / f'xtlr_Data/StreamingAssets/InstallResource/{patch.name}'] if path.is_file()), None)
        record = {'code': code, 'name': outfit['name'], 'patch_bundle': patch.relative_to(game).as_posix(),
                  'patch_sha256': digest(patch), 'changed_textures': [], 'outputs': []}
        report['items'].append(record)
        try:
            if base is None:
                raise FileNotFoundError(f'No baseline bundle for {patch.name}')
            record.update(base_bundle=base.relative_to(game).as_posix(), base_sha256=digest(base))
            names = {code + '_B', code + '_b'} | {layer['name'] for layer in outfit['card']['layers']}
            baseline, patched = textures(base, names), textures(patch, names)
            cover = next((name for name in [code + '_B', code + '_b'] if name in baseline), None)
            needed = {layer['name'] for layer in outfit['card']['layers']}
            if cover:
                needed.add(cover)
            else:
                raise ValueError('No source cover found')
            # Validate all selected replacements before writing any file for this disc.
            for name in sorted(needed):
                if name not in baseline or name not in patched:
                    raise ValueError(f'Missing matching texture: {name}')
                if baseline[name].size != patched[name].size:
                    raise ValueError(f'Texture dimensions differ: {name}')
                before, after = pixel_digest(baseline[name]), pixel_digest(patched[name])
                if before != after:
                    record['changed_textures'].append({'name': name, 'size': list(patched[name].size),
                                                      'base_rgba_sha256': before, 'patch_rgba_sha256': after})
            changed = {entry['name'] for entry in record['changed_textures']}
            if not apply or not changed:
                continue

            def publish(path, image, size=None, quality=93):
                target = asset_path(output, path)
                image = image.copy()
                if size:
                    image.thumbnail((size, size), Image.Resampling.LANCZOS)
                save_changed(target, image_bytes(image, 'WEBP', quality=quality, method=5))
                record['outputs'].append({'path': path, 'size': list(image.size), 'sha256': digest(target)})

            if cover in changed:
                image = patched[cover]
                publish(outfit.get('fullCover') or f'/art/{code}/full.webp', image)
                if asset_path(output, outfit['cover']).exists():
                    publish(outfit['cover'], image, 1400, 91)
                publish(outfit['thumbnail'], image, 280, 91)
                preview = asset_path(output, f'/art/{code}/preview.jpg')
                # Use the same compositing and encoding as the normal OG export.
                preview.parent.mkdir(parents=True, exist_ok=True)
                buffer = io.BytesIO()
                save_preview(image, buffer)
                save_changed(preview, buffer.getvalue())
                record['outputs'].append({'path': f'/art/{code}/preview.jpg', 'sha256': digest(preview)})
                original = image_bytes(image, 'PNG')
                if outfit['staticImage'].startswith('/'):
                    save_changed(asset_path(output, outfit['staticImage']), original)
                if originals is not None:
                    target = originals / f'{code}.png'
                    save_changed(target, original)
                    record['download_original'] = {'name': target.name, 'sha256': digest(target),
                                                   'rgba_sha256': pixel_digest(image), 'size': list(image.size)}
            for layer in outfit['card']['layers']:
                if layer['name'] not in changed:
                    continue
                image = patched[layer['name']].copy()
                target = asset_path(output, layer['path'])
                if target.exists():
                    with Image.open(target) as existing:
                        image = image.resize(existing.size, Image.Resampling.LANCZOS)
                publish(layer['path'], image, quality=91)
        except Exception as exc:
            report['errors'].append({'code': code, 'error': str(exc)})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, default=GAME)
    parser.add_argument('--public-dir', type=Path, default=REPOSITORY / 'public')
    parser.add_argument('--work-dir', type=Path, default=REPOSITORY / '.build/patch-artwork')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--apply', action='store_true', help='Export verified replacements; default is audit only.')
    args = parser.parse_args()
    game = args.game_dir.resolve()
    public, work = protect_output(args.public_dir, game), protect_output(args.work_dir, game)
    outfits = json.loads((public / 'data/outfits.json').read_text(encoding='utf8'))
    report = apply_patches(outfits, game, public, work / 'originals', args.apply)
    target = protect_output(args.report or work / 'report.json', game)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    changed = [item for item in report['items'] if item['changed_textures']]
    print(f'{len(report["items"])} patched discs checked; {len(changed)} have changed website textures; '
          f'{len(report["errors"])} errors. Applied: {args.apply}')
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
