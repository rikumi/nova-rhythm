import UnityPy,json,collections
from pathlib import Path
from pipeline_paths import ROOT, GAME
p=GAME/'Persistent_Store/AssetBundles/audio.unity3d'
e=UnityPy.load(str(p));rows=[]
for o in e.objects:
 if o.type.name=='MonoBehaviour':
  d=o.read_typetree();
  if 'objectName' in d: rows.append(d)
(ROOT/'data/wwise_objects.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
ids={int(v) for r in json.loads((ROOT/'data/inventory.json').read_text(encoding='utf8'))['entries'] for g in r.get('gamesyncs',[]) for v in [g['group_id'],g['value_id']]}
print('\n'.join(str({k:v for k,v in r.items() if k in ['id','objectName','groupID','groupName']}) for r in rows if r.get('id') in ids)[:13000])
