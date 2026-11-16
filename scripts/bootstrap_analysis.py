"""Seed historical analysis inputs in a separate workspace, relocating references."""
import argparse
import json
from pathlib import Path
import shutil
from pipeline_paths import REPOSITORY, protect_output


def relocate(value, game, work):
    if isinstance(value, list):
        return [relocate(v, game, work) for v in value]
    if isinstance(value, dict):
        return {k: relocate(v, game, work) for k, v in value.items()}
    if isinstance(value, str):
        if '{{GAME}}' in value or '{{WORK}}' in value:
            return value.replace('\\', '/').replace('{{GAME}}', game.as_posix()).replace('{{WORK}}', work.as_posix())
        return value
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, default=REPOSITORY/'.build/analysis')
    args = parser.parse_args()
    game = args.game_dir.resolve(); work = protect_output(args.work_dir, game)
    if work == REPOSITORY or work in REPOSITORY.parents:
        parser.error('Use an isolated analysis directory.')
    (work/'data').mkdir(parents=True, exist_ok=True)
    for source in (REPOSITORY/'references/analysis').glob('*.json'):
        target = work/'data'/source.name
        if not target.exists():
            data = relocate(json.loads(source.read_text(encoding='utf8')), game, work)
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
    routes = json.loads((REPOSITORY/'references/routes.json').read_text(encoding='utf8'))['entries']
    supplemental = []
    for route in routes:
        if route.get('source') != 'regenerated_version' or route.get('parent_id'):
            continue
        recipe = (REPOSITORY/'references'/route['recipe_file']).read_text(encoding='utf8').replace('{{GAME}}', game.as_posix())
        path = work/'data/reference_txtp'/(route['id']+'.txtp')
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(recipe, encoding='utf8')
        supplemental.append(route | {'recipe': recipe, 'path': str(path), 'status': 'inventoried'})
    target = work/'data/supplemental_inventory.json'
    if not target.exists():
        target.write_text(json.dumps(supplemental, ensure_ascii=False, indent=2), encoding='utf8')
    # Source copies are inputs for native hardware generation and font subsetting.
    (work/'src').mkdir(exist_ok=True)
    for source in (REPOSITORY/'src').glob('*'):
        target = work/'src'/source.name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
    print(f'Research workspace: {work}')
    print(f'Set NOVA_GAME_DIR={game} and NOVA_WORK_DIR={work} before running research scripts.')


if __name__ == '__main__':
    main()
