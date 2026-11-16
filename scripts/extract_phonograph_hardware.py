"""Export static phonograph sprites with their exact UI RectTransform values."""
from pathlib import Path
import json, math, struct, zlib
import UnityPy

from pipeline_paths import ROOT
from pipeline_paths import GAME
SOURCE=GAME/'Persistent_Store/AssetBundles/ui_disc.unity3d'
env=UnityPy.load(str(SOURCE))
objects={o.path_id:o for o in env.objects}
go_names = {o.path_id: o.read_typetree()['m_Name'] for o in env.objects if o.type.name == 'GameObject'}
note = {}
for obj in env.objects:
    if obj.type.name not in ['ParticleSystem', 'MonoBehaviour']:
        continue
    data = obj.read_typetree(); go_name = go_names.get(data.get('m_GameObject', {}).get('m_PathID'))
    if obj.type.name == 'ParticleSystem' and go_name == 'Music':
        size = data['InitialModule']['startSize']; note.update({'min_size': size['minScalar'], 'max_size': size['scalar']})
    if obj.type.name == 'MonoBehaviour' and go_name == 'UIParticleNote' and 'm_Scale3D' in data:
        note['ui_scale'] = data['m_Scale3D']['x']
references=json.loads((ROOT/'data/native_hardware_story.json').read_text(encoding='utf8'))
names={'img1':'slider','img2':'knob-pointer','img3':'right-clamp','img4':'left-clamp'}
rows=[]
clip = next(o.read_typetree() for o in env.objects if o.type.name == 'AnimationClip' and o.read_typetree().get('m_Name') == 'Music_in')
stream = clip['m_MuscleClip']['m_Clip']['data']['m_StreamedClip']['data']
packed = struct.pack('<' + 'I' * len(stream), *stream)
cursor = 0; final_keys = {}; pose_time = 0
while cursor + 8 <= len(packed):
    moment, count = struct.unpack_from('<fI', packed, cursor); cursor += 8
    keys = {}
    for _ in range(count):
        index, _, _, _, value = struct.unpack_from('<Iffff', packed, cursor); cursor += 20
        keys[index] = value
    if math.isfinite(moment) and moment >= pose_time:
        final_keys.update(keys); pose_time = moment
pose = {}; offset = 0
for binding in clip['m_ClipBindingConstant']['genericBindings']:
    width = (4 if binding['attribute'] == 2 else 3) if binding['typeID'] == 4 else 1
    pose[(binding['path'], binding['attribute'])] = [final_keys.get(offset + i) for i in range(width)]
    offset += width
for row in references:
    if '/imgPhonograph/' not in row['path']:continue
    key=names[row['path'].split('/')[-1]]
    sprite=objects[row['sprite']['m_PathID']].read()
    target=ROOT/'public/ui'/('phonograph-'+key+'.png')
    sprite.image.save(str(target))
    rect=row['rect'];q=rect['m_LocalRotation']
    angle=math.degrees(math.atan2(2*q['w']*q['z'],1-2*q['z']**2))
    y = rect['m_AnchoredPosition']['y']
    native_path = 'imgPhonograph/' + row['path'].split('/')[-1]
    path_hash = zlib.crc32(native_path.encode('utf8'))
    if key == 'slider':
        y = pose[(path_hash, zlib.crc32(b'm_AnchoredPosition.y'))][0]
    if key == 'knob-pointer':
        angle = pose[(path_hash, 4)][2]
    rows.append({'name':key,'src':'/ui/'+target.name,'x':rect['m_AnchoredPosition']['x'],
                 'y':y,'width':rect['m_SizeDelta']['x'],
                 'height':rect['m_SizeDelta']['y'],'pivot':rect['m_Pivot'],
                 'rotation':round(angle,5),'flip_x':rect['m_LocalScale']['x'],
                 'opacity':row['color']['a']})
(ROOT/'data/phonograph_hardware.json').write_text(json.dumps({'source':str(SOURCE),'reference_size':[1052,710], 'pose_animation':'Music_in', 'pose_time':pose_time, 'sprites':rows, 'note':note},ensure_ascii=False,indent=2),encoding='utf8')
(ROOT/'src/nativePhonograph.ts').write_text('// Generated from ui_disc RectTransforms and Music_in end pose; run scripts/extract_phonograph_hardware.py.\nexport const PHONOGRAPH_HARDWARE = '+json.dumps(rows,ensure_ascii=False,indent=2)+' as const;\nexport const PHONOGRAPH_NOTE = '+json.dumps(note)+' as const;\n',encoding='utf8')
print('exported',len(rows),'static hardware sprites')
