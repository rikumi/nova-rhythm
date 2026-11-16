from pathlib import Path
import json,re,concurrent.futures,hashlib
import UnityPy
from pipeline_paths import ROOT;from pipeline_paths import GAME as G
names={o['id']:o['objectName'] for o in json.loads((ROOT/'data/wwise_objects.json').read_text(encoding='utf8'))}
def inspect(p):
 result=[]
 try:
  e=UnityPy.load(str(p));gos={o.path_id:o.read().m_Name for o in e.objects if o.type.name=='GameObject'}
  for o in e.objects:
   if o.type.name!='MonoBehaviour':continue
   d=o.read_typetree();group=d.get('_WwiseStateGroup');value=d.get('_WwiseStateGroupSate');event=d.get('_WiseEvent')
   state=d.get('WwiseState',{})
   if not group and isinstance(state,dict) and state.get('groupIdInternal'):
    group=names.get(state['groupIdInternal']);value=names.get(state.get('idInternal'))
   if not event and isinstance(d.get('WiseEvent'),dict):event=names.get(d['WiseEvent'].get('idInternal'))
   if not group and not event:continue
   result.append({'bundle':str(p),'path_id':o.path_id,'game_object':gos.get(d.get('m_GameObject',{}).get('m_PathID')),'group':group,'value':value,'event':event,'trigger_type':d.get('_EventTriggerType'),'delay_seconds':d.get('_delayTime'),'raw':d})
 except Exception as ex:result.append({'bundle':str(p),'error':str(ex)})
 return result
def main():
 files={p.name:p for p in (G/'xtlr_Data/StreamingAssets/InstallResource').glob('ui*.unity3d')}
 files.update({p.name:p for p in (G/'Persistent_Store/AssetBundles').glob('ui*.unity3d')})
 rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for i,rs in enumerate(pool.map(inspect,files.values()),1):
   rows.extend(rs)
   if i%25==0:print(i,'/',len(files),len(rows),'audio components',flush=True)
 (ROOT/'data/unity_audio_usages.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print('done',len(rows),flush=True)
if __name__=='__main__':main()
