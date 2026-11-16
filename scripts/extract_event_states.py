from pathlib import Path
import json,struct,collections
from pipeline_paths import ROOT;from pipeline_paths import GAME
names={o['id']:o['objectName'] for o in json.loads((ROOT/'data/wwise_objects.json').read_text(encoding='utf8'))}
rows=[]
for origin,base in [('install',GAME/'xtlr_Data/StreamingAssets/InstallResource'),('version',GAME/'Persistent_Store/SoundBanks')]:
 for p in base.glob('*.bnk'):
  data=p.read_bytes();off=0;objects={}
  while off+8<=len(data):
   tag=data[off:off+4];size=struct.unpack_from('<I',data,off+4)[0];chunk=data[off+8:off+8+size];off+=8+size
   if tag!=b'HIRC':continue
   pos=4
   for i in range(struct.unpack_from('<I',chunk)[0]):
    typ=chunk[pos];n=struct.unpack_from('<I',chunk,pos+1)[0];body=chunk[pos+5:pos+5+n];pos+=5+n
    if len(body)>=4:objects[struct.unpack_from('<I',body)[0]]=(typ,body)
  for oid,(typ,body) in objects.items():
   if typ!=4 or len(body)<5:continue
   n=body[4];actions=body[5:];sets=[]
   if len(actions)!=n*4:continue
   for aid in struct.unpack('<'+'I'*n,actions):
    a=objects.get(aid)
    if not a or a[0]!=3:continue
    ab=a[1]
    if len(ab)<14:continue
    action=struct.unpack_from('<H',ab,4)[0]
    if action!=0x1204:continue
    g,v=struct.unpack_from('<II',ab,len(ab)-8)
    sets.append({'group_id':g,'group':names.get(g),'value_id':v,'value':names.get(v)})
   if sets:rows.append({'source':origin,'bank':p.name,'event_id':oid,'event':names.get(oid),'sets':sets})
(ROOT/'data/wwise_event_states.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print(len(rows),collections.Counter(r['bank'] for r in rows).most_common(12));print(next((r for r in rows if r['event']=='forest_explore_setState'),None))
