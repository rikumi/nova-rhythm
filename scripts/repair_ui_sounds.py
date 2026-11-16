"""Resolve embedded BNK sounds in project recipes, then export used UI effects."""
import json
import re
import subprocess
from pathlib import Path
from export_audio import prepare, ROOT, CLI

used = set(re.findall(r"sound\('([^']+)'\)", (ROOT/'src/main.tsx').read_text(encoding='utf8')))
exports = json.loads((ROOT/'data/ui_sound_exports.json').read_text(encoding='utf8'))
for row in exports:
    if row['event'] not in used:
        continue
    path = ROOT/row['recipe']
    body = '\n'.join(line for line in path.read_text(encoding='utf8').splitlines() if not line.lstrip().startswith('#'))
    _, recipe, _ = prepare({'path': str(path), 'recipe': body})
    fixed = ROOT/'data/generated/sfx'/(row['event']+'.txtp')
    fixed.write_text(recipe, encoding='utf8')
    result = subprocess.run([str(CLI), '-i', '-o', str(ROOT/'public'/row['path'].lstrip('/')), str(fixed)], capture_output=True)
    row['ok'] = result.returncode == 0
    if not row['ok']:
        raise RuntimeError(row['event'] + ': ' + result.stderr.decode('utf8', errors='replace'))
(ROOT/'data/ui_sound_exports.json').write_text(json.dumps(exports, ensure_ascii=False, indent=2), encoding='utf8')
print('Exported', len(used), 'used game UI effects')
