"""Read game icon bundles and export home icons and compact music manifests."""
from pathlib import Path
import json
import runpy
import UnityPy

from pipeline_paths import ROOT, REPOSITORY
from pipeline_paths import GAME
sources = {}
for directory in [GAME/'xtlr_Data/StreamingAssets/InstallResource', GAME/'Persistent_Store/AssetBundles']:
    for p in directory.glob('*.unity3d'):
        if p.name.startswith(('icon-', 'image-', 'ui_common', 'ui_mainview')):
            sources[p.name] = p
references = {-4481801100318917440: 'outfit'}
rows = []
for p in sources.values():
    env = UnityPy.load(str(p))
    for obj in env.objects:
        if obj.type.name != 'Sprite':
            continue
        sprite = obj.read()
        if obj.path_id in references:
            target = ROOT/'public/ui'/f'home-{sprite.m_Name}.png'
            image = sprite.image
            image.save(str(target))
            rows.append({'category': references[obj.path_id], 'name': sprite.m_Name, 'path': '/ui/'+target.name, 'source': str(p), 'path_id': obj.path_id, 'width': image.width, 'height': image.height})
        if sprite.m_Name == 'db_favor_profile':
            border = sprite.m_Border
            (ROOT/'data/story_button_slicing.json').write_text(json.dumps({
                'name': sprite.m_Name, 'source': str(p), 'path_id': obj.path_id,
                'width': sprite.m_Rect.width, 'height': sprite.m_Rect.height,
                'border': {'left': border.x, 'bottom': border.y, 'right': border.z, 'top': border.w},
                'css_slice': [border.w, border.z, border.y, border.x],
            }, indent=2), encoding='utf8')
runpy.run_path(str(REPOSITORY/'scripts/extract_home_native.py'), run_name='__main__')
native = json.loads((ROOT/'data/home_native_icons.json').read_text(encoding='utf8'))['story']
rows.append({'category': 'library', 'name': 'MainView Story RootSD', 'path': '/ui/home-native-story.svg',
             'source': native['source'], 'root': native['root'], 'layers': len(native['layers'])})
(ROOT/'data/home_icons.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')
from prepare_library import main as prepare_library
prepare_library()
print(json.dumps(rows, ensure_ascii=False, indent=2))
