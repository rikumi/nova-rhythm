from pathlib import Path
import json,re,itertools,copy
from pipeline_paths import ROOT as root
rows=json.loads((root/'data/inventory.json').read_text(encoding='utf8'))['entries']+json.loads((root/'data/supplemental_inventory.json').read_text(encoding='utf8'));variants=[]
for r in rows:
 if not r.get('random'):continue
 matches=list(re.finditer(r'(-R)(\d+)>(\d+|-)',r['recipe']))
 for choices in itertools.product(*(range(1,int(m[2])+1) for m in matches)):
  n=copy.deepcopy(r);n['parent_id']=r['id'];n['random_choices']=list(choices);n['id']=r['id']+'-r'+''.join(map(str,choices))
  counter=iter(choices);n['recipe']=re.sub(r'(-R)(\d+)>(\d+|-)',lambda m:m[1]+m[2]+'>'+str(next(counter)),r['recipe'])
  variants.append(n)
(root/'data/audio_variants.json').write_text(json.dumps(variants,ensure_ascii=False,indent=2),encoding='utf8');print(len(variants))
