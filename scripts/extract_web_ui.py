from pathlib import Path
import json,re,concurrent.futures
import UnityPy
from pipeline_paths import ROOT;from pipeline_paths import GAME as G;A=G/'xtlr_Data/StreamingAssets/InstallResource';V=G/'Persistent_Store/AssetBundles'
e=UnityPy.load(str(V/'ui_disc.unity3d'));gos={o.path_id:o.read_typetree()['m_Name'] for o in e.objects if o.type.name=='GameObject'};wanted={};names=['imgPhonograph','----Bg----','imgDiscFrame','imgOn1','imgOff1','imgTitle','imgBg','Image (1)']
transforms={o.path_id:o.read_typetree() for o in e.objects if o.type.name in ['RectTransform','Transform']}
bygo={d['m_GameObject']['m_PathID']:tid for tid,d in transforms.items()}
def ancestors(goid):
 result=[];tid=bygo.get(goid)
 while tid in transforms:
  t=transforms[tid];result.append(gos.get(t['m_GameObject']['m_PathID'],''));tid=t['m_Father']['m_PathID']
 return result
for o in e.objects:
 if o.type.name!='MonoBehaviour':continue
 d=o.read_typetree();go=gos.get(d.get('m_GameObject',{}).get('m_PathID'),'')
 if (go in names or any(n in ancestors(d.get('m_GameObject',{}).get('m_PathID')) for n in ['rtSideBBg','rtSideABg','UIParticleNote'])) and d.get('m_Sprite',{}).get('m_PathID'):
  pid=d['m_Sprite']['m_PathID'];wanted.setdefault(pid,[]).append(go)
(ROOT/'data/ui_wanted_sprites.json').write_text(json.dumps({str(k):v for k,v in wanted.items()},ensure_ascii=False,indent=2),encoding='utf8')
files={p.name:p for p in A.glob('*.unity3d') if p.name.startswith(('image-','icon-','ui_common','ui_disc','ui_big_sprites'))};files.update({p.name:p for p in V.glob('*.unity3d') if p.name.startswith(('image-','icon-','ui_common','ui_disc','ui_big_sprites'))})
out=ROOT/'public/ui';out.mkdir(parents=True,exist_ok=True)
def scan(p):
 rows=[]
 try:
  env=UnityPy.load(str(p))
  for o in env.objects:
   if o.type.name!='Sprite' or o.path_id not in wanted:continue
   s=o.read();target=out/(s.m_Name+'.png');s.image.save(str(target));rows.append({'name':s.m_Name,'path':'/ui/'+target.name,'ui_nodes':wanted[o.path_id],'source_bundle':str(p),'path_id':o.path_id})
 except Exception as ex:rows.append({'error':str(ex),'bundle':str(p)})
 return rows
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for i,res in enumerate(pool.map(scan,files.values()),1):
  rows.extend(res)
  if i%20==0:print(i,'/',len(files),'found',len(rows),flush=True)
(ROOT/'data/ui_sprites.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print('done',len(rows),flush=True)
