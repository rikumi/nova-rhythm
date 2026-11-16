"""Render TXTP recipes using read-only game inputs. All writes stay under project root."""
from pathlib import Path
import json,re,hashlib,subprocess,concurrent.futures,os,time
import imageio_ffmpeg
from pipeline_paths import ROOT
from pipeline_paths import CLI
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
def load(p,default=None):
 return json.loads((ROOT/p).read_text(encoding='utf8')) if (ROOT/p).exists() else default
def save(p,d):
 p=ROOT/p;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(p)
def prepare(row):
 lines=[];deps=[]
 for line in row['recipe'].splitlines():
  # Ignore annotation comments, retain vgmstream directives beginning with a single #.
  line=line.split('##')[0].rstrip()
  if line.lstrip().startswith('#'):continue
  m=re.match(r'^(\s*)(.*?\.(?:wem|bnk))(?=\s|$)(.*)$',line)
  if m:
   p=(Path(row['path']).parent/m[2]).resolve()
   if not p.exists() and p.suffix.lower()=='.bnk' and (p.parent.parent/p.name).exists():
    p=p.parent.parent/p.name
   if not p.exists():raise FileNotFoundError(p)
   s=p.stat();deps.append((str(p),s.st_size,s.st_mtime_ns))
   line=m[1]+str(p).replace('\\','/')+m[3]
  lines.append(line)
 recipe='\n'.join(lines)+'\n';signature=hashlib.sha256(json.dumps([recipe,deps,'vgmstream-r2168-ignore-loop-pcm16-flac-v1']).encode()).hexdigest()
 return signature,recipe,deps
def run_one(job):
 key,recipe,deps=job
 staging=ROOT/'data/render';staging.mkdir(parents=True,exist_ok=True)
 txtp=staging/(key+'.txtp');txtp.write_text(recipe,encoding='utf8')
 wav=staging/(key+'.wav');dest=ROOT/'music/_rendered'/(key+'.flac');dest.parent.mkdir(parents=True,exist_ok=True)
 result={'key':key,'recipe_path':str(txtp.relative_to(ROOT)),'dependencies':deps}
 try:
  meta=subprocess.run([str(CLI),'-I','-m',str(txtp)],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=45)
  result['metadata_raw']=meta.stdout;result['metadata_error']=meta.stderr
  p=subprocess.run([str(CLI),'-i','-o',str(wav),str(txtp)],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180)
  if p.returncode or not wav.exists():raise RuntimeError(p.stderr+'\n'+p.stdout)
  p=subprocess.run([FFMPEG,'-v','error','-y','-i',str(wav),'-c:a','flac','-compression_level','8',str(dest)],capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError(p.stderr)
  # Stream hash detects exact PCM duplicates across different Wwise recipe/event aliases.
  p=subprocess.run([FFMPEG,'-v','error','-i',str(dest),'-f','hash','-hash','sha256','-'],capture_output=True,text=True,timeout=90)
  if p.returncode:raise RuntimeError(p.stderr)
  result.update(status='exported',audio_path=str(dest.relative_to(ROOT)),size=dest.stat().st_size,pcm_sha256=p.stdout.strip().split('=')[-1])
  wav.unlink()
 except Exception as ex:result.update(status='failed',error=str(ex))
 return result
def main():
 rows=load('data/inventory.json')['entries']+load('data/audio_variants.json',[])+load('data/supplemental_inventory.json',[]);state=load('data/export_state.json',{'schema_version':1,'renders':{},'entries':{}});jobs={}
 names={o['id']:o['objectName'] for o in load('data/wwise_objects.json')}
 for r in rows:
  if r['status']!='inventoried':continue
  if any(names.get(g['value_id'],'').lower()=='transition' for g in r['gamesyncs']):
   state['entries'][r['id']]={'status':'excluded_transition_state'};continue
  try:
   key,recipe,deps=prepare(r);state['entries'][r['id']]={'key':key}
   old=state['renders'].get(key,{})
   if old.get('status')=='exported' and (ROOT/old['audio_path']).exists():continue
   jobs[key]=(key,recipe,deps)
  except Exception as ex:state['entries'][r['id']]={'status':'failed','error':str(ex)}
 save('data/export_state.json',state);print('recipes to render',len(jobs),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  futs={pool.submit(run_one,j):k for k,j in jobs.items()}
  for i,f in enumerate(concurrent.futures.as_completed(futs),1):
   result=f.result();state['renders'][result['key']]=result;save('data/export_state.json',state)
   if i%20==0 or result['status']!='exported':print(i,'/',len(jobs),result['status'],result.get('error','')[:300],flush=True)
 print('done',flush=True)
if __name__=='__main__':main()
