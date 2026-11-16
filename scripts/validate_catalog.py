"""Validate exported references and unchanged TXTP source files; never writes to game paths."""
from pathlib import Path
import hashlib
import json
from analyze import ROOT, load, save


def main():
    errors = []
    catalog = load('data/catalog.json')['tracks']
    for row in catalog:
        if row['status'] != 'exported' or not (ROOT / row['audio_path']).is_file():
            errors.append({'track': row['id'], 'error': 'missing_export'})
        if not row['audio']['sample_rate'] or not row['audio']['number_of_samples']:
            errors.append({'track': row['id'], 'error': 'invalid_audio_metadata'})
        if 'transition' in row['source_filename'].lower():
            errors.append({'track': row['id'], 'error': 'transition_in_catalog'})
    manifest = load('public/data/outfits.json')['items']
    for item in manifest:
        if len(item['music']) != 2:
            errors.append({'item': item['id'], 'error': 'requires_main_and_victory'})
        draws = []
        for layer in item['card']['layers']:
            if not (ROOT / ('public' + layer['path'])).exists():
                errors.append({'item': item['id'], 'error': 'missing_web_layer'})
            draws.append(json.dumps({k: layer[k] for k in ['name', 'x', 'y', 'width', 'height', 'pivot', 'rotation', 'opacity']}, sort_keys=True))
        if len(draws) != len(set(draws)):
            errors.append({'item': item['id'], 'error': 'exact_duplicate_draw'})
    dates = [item['activity']['date'] for item in manifest]
    if dates != sorted(dates, reverse=True):
        errors.append({'error': 'activity_order_not_descending'})
    source_checked = 0
    for row in load('data/inventory.json')['entries']:
        p = Path(row['path'])
        if row.get('sha256'):
            if not p.exists() or hashlib.file_digest(p.open('rb'), 'sha256').hexdigest() != row['sha256']:
                errors.append({'path': str(p), 'error': 'source_changed_since_snapshot'})
            source_checked += 1
    report = {'catalog_routes': len(catalog), 'unique_audio_paths': len({t['audio_path'] for t in catalog}),
              'outfit_items': len(manifest), 'web_native_layers': sum(len(d['card']['layers']) for d in manifest),
              'source_txtp_sha256_checked': source_checked, 'errors': errors}
    save('data/validation.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
