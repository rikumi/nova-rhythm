"""Export the exact texture referenced by ui_disc's Music particle material."""
from pathlib import Path
import json
import UnityPy

from pipeline_paths import ROOT
from pipeline_paths import GAME
INSTALL = GAME / 'xtlr_Data/StreamingAssets/InstallResource'
VERSION = GAME / 'Persistent_Store/AssetBundles'
TARGET_MATERIAL = 2882582292074277227
TARGET_CAB = 'CAB-ff6839bdaa0a08f6894d50a977c8fe86'


def main():
    files = {p.name: p for p in INSTALL.glob('*.unity3d')}
    files.update({p.name: p for p in VERSION.glob('*.unity3d')})
    candidates = sorted(files.values(), key=lambda p: (not p.name.startswith(('icon-', 'ui_common', 'image-', 'ui_big_sprites')), p.stat().st_size))
    for index, p in enumerate(candidates):
        env = UnityPy.load(str(p))
        target = next((o for o in env.objects if o.path_id == TARGET_MATERIAL and o.type.name == 'Material'), None)
        if target is None:
            continue
        material = target.read()
        data = target.read_typetree()
        texenv = dict(data['m_SavedProperties']['m_TexEnvs'])['_MainTex']
        ptr = dict(material.m_SavedProperties.m_TexEnvs)['_MainTex'].m_Texture
        texture = ptr.read()
        dest = ROOT / 'public/ui/particle_music_notes.png'
        texture.image.save(str(dest))
        evidence = {'source_bundle': str(p), 'material_id': TARGET_MATERIAL, 'material_name': data['m_Name'],
                    'texture_name': texture.m_Name, 'texture_reference': texenv,
                    'texture_size': [texture.m_Width, texture.m_Height],
                    'particle_system': 'UIParticleNote/Music', 'tiles': [2, 1],
                    'output': str(dest.relative_to(ROOT))}
        (ROOT / 'data/native_note_texture.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps(evidence, ensure_ascii=False), flush=True)
        return
    raise RuntimeError('Music particle material was not found')


if __name__ == '__main__':
    main()
