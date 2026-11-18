"""Extract disc covers, parallax layer textures and prefab transforms without editing sources."""
from pathlib import Path
import json,re,concurrent.futures,hashlib
import UnityPy
from pipeline_paths import ROOT;from pipeline_paths import GAME
INSTALL=GAME/'xtlr_Data/StreamingAssets/InstallResource';VERSION=GAME/'Persistent_Store/AssetBundles'
def extract(job):
 did,p=job;folder=ROOT/'assets/outfit'/did;folder.mkdir(parents=True,exist_ok=True)
 result={'extraction_version':2,'disc_code':did,'source_bundle':str(p),'source_sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'images':[],'prefabs':[],'errors':[]}
 prior=folder/'manifest.json'
 if prior.exists():
  old=json.loads(prior.read_text(encoding='utf8'))
  if old.get('extraction_version')==2 and old.get('source_sha256')==result['source_sha256'] and all((ROOT/i['path']).exists() for i in old['images']):return old
 e=UnityPy.load(str(p));scene=[]
 pathmap={ptr.path_id:path for path,ptr in e.container.items()}
 for o in e.objects:
  try:
   if o.type.name=='Texture2D':
    t=o.read();name=t.m_Name
    # Gyroscope sprites can have unprefixed names such as bg, title, 01 or 02.
    if not name or '/' in name or '\\' in name:continue
    dest=folder/(name+'.png');t.image.save(str(dest))
    result['images'].append({'name':name,'path':str(dest.relative_to(ROOT)).replace('\\','/'),'width':t.m_Width,'height':t.m_Height,'role':'cover' if name.lower()==did+'_b' else 'parallax_layer','path_id':o.path_id,'asset_path':pathmap.get(o.path_id)})
   elif o.type.name in ['GameObject','Transform','RectTransform','SpriteRenderer']:
    scene.append({'type':o.type.name,'path_id':o.path_id,'data':o.read_typetree()})
   elif o.type.name=='MonoBehaviour':
    d=o.read_typetree()
    # Keep small motion configuration; exclude Cubism mesh arrays and particle payloads.
    if any(re.search(r'gyro|parallax|offset|movement|rotate|depth',k,re.I) for k in d):scene.append({'type':o.type.name,'path_id':o.path_id,'data':d})
  except Exception as ex:result['errors'].append({'path_id':o.path_id,'error':str(ex)})
 if scene:
  dest=folder/'parallax_scene.json';dest.write_text(json.dumps(scene,ensure_ascii=False,indent=2,default=lambda v:list(v) if isinstance(v,bytes) else str(v)),encoding='utf8');result['scene_path']=str(dest.relative_to(ROOT)).replace('\\','/')
 prior.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
def main():
 ip=json.loads((ROOT/'data/upstream/tables/CN/bin/DiscIP.json').read_text(encoding='utf8'));ids={v['VoFile'].split('_')[-1] for v in ip.values()};jobs=[];missing=[]
 for did in sorted(ids):
  name='disc_'+did+'.unity3d';p=VERSION/name
  if not p.exists():p=INSTALL/name
  if not p.exists():missing.append(did);continue
  jobs.append((did,p))
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for i,result in enumerate(pool.map(extract,jobs),1):
   results.append(result)
   if i%10==0:print(i,'/',len(jobs),flush=True)
 out={'schema_version':1,'discs':results,'missing_bundles':missing}
 (ROOT/'data/artwork.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print('images',sum(len(r['images']) for r in results),'missing',missing,flush=True)
if __name__=='__main__':main()
