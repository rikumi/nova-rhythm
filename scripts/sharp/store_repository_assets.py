"""Version runtime assets on an isolated branch, leaving the main worktree alone."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'.build/repository-assets'
GH=ROOT/'tools/github-cli/portable/bin/gh.exe'
REPOSITORY='rikumi/nova-rhythm'


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def command(*args):
    result=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    if result.returncode:raise RuntimeError(result.stderr)
    return result.stdout.strip()


def git(*args):return command('git','-C',WORK,*args)


def push():
    print('Pushing asset commit',git('rev-parse','--short','HEAD'),flush=True)
    git('-c','core.compression=0','-c','pack.window=0','-c','credential.helper=',
        '-c',f'credential.helper=!{GH.as_posix()} auth git-credential','push','origin','site-assets')


def run():
    if git('branch','--show-current')!='site-assets':raise RuntimeError('Expected isolated site-assets worktree')
    results=json.loads((ROOT/'references/sharp-scenes-results.json').read_text(encoding='utf8'))
    if not results['publication'].get('verified'):raise RuntimeError('Unverified source models')
    pages=json.loads(command(GH,'api',f'repos/{REPOSITORY}/releases/446269099/assets?per_page=100','--paginate','--slurp'))
    artwork={asset['name']:asset for page in pages for asset in page}
    catalog=json.loads((ROOT/'public/data/outfits.json').read_text(encoding='utf8'))['items']
    names={item['code']+'.png' for item in catalog}
    if names!=set(artwork):raise RuntimeError('Artwork selection differs from the runtime catalog')
    images=WORK/'artwork';images.mkdir(exist_ok=True)
    for name,asset in artwork.items():
        cached=ROOT/'.build/layering-trial'/name[:4]/'original.png'
        if not (images/name).exists() and cached.exists() and 'sha256:'+digest(cached)==asset['digest']:
            shutil.copyfile(cached,images/name)
    command(GH,'release','download','artwork','--repo',REPOSITORY,'--pattern','*.png','--dir',images,'--skip-existing')
    for name,asset in artwork.items():
        if 'sha256:'+digest(images/name)!=asset['digest']:raise RuntimeError('Artwork hash mismatch: '+name)
    print('Verified',len(artwork),'original images',flush=True)
    models=WORK/'models';models.mkdir(exist_ok=True)
    pending=[];manifest={'schemaVersion':1,'outfits':{},'artwork':{}}
    for code,scene in sorted(results['outfits'].items()):
        name=scene['scene_url'].rsplit('/',1)[-1];target=models/name
        source=ROOT/'.build/sharp-layering/batch/release-assets'/name
        if not target.exists():shutil.copyfile(source,target)
        if target.stat().st_size>=100*1024**2 or digest(target)!=scene['compressed_sha256']:
            raise RuntimeError('Invalid scene asset: '+name)
        manifest['outfits'][code]={**scene,'scene_url':'models/'+name}
        if not git('ls-files','--',str(target.relative_to(WORK)).replace('\\','/')):pending.append(target)
    for start in range(0,len(pending),8):
        batch=pending[start:start+8]
        git('add','--',*[path.relative_to(WORK).as_posix() for path in batch])
        git('commit','-m',f'Version SHARP models {start+1}-{start+len(batch)} of {len(pending)}')
        push()
    for name,asset in artwork.items():
        manifest['artwork'][name]={'path':'artwork/'+name,'sha256':asset['digest'].removeprefix('sha256:'),'bytes':asset['size']}
    (WORK/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    shutil.copyfile(ROOT/'.build/sharp-layering/ml-sharp/LICENSE_MODEL',WORK/'APPLE_SHARP_LICENSE_MODEL.txt')
    git('add','--','artwork','manifest.json','APPLE_SHARP_LICENSE_MODEL.txt')
    if git('status','--porcelain'):
        git('commit','-m','Version all 106 original artworks and the verified scene index')
    push()
    revision=git('rev-parse','HEAD')
    remote=json.loads(command(GH,'api',f'repos/{REPOSITORY}/git/trees/{revision}?recursive=1'))
    local={}
    for line in git('ls-tree','-rl',revision).splitlines():
        fields,path=line.split('\t',1);mode,kind,sha,size=fields.split()
        local[path]=(sha,int(size))
    stored={item['path']:(item['sha'],item['size']) for item in remote['tree'] if item['type']=='blob'}
    if remote.get('truncated') or stored!=local:raise RuntimeError('Remote Git asset tree differs from verified local files')
    record={'schemaVersion':1,'repository':REPOSITORY,'branch':'site-assets','commit':revision,
        'raw_base':f'https://raw.githubusercontent.com/{REPOSITORY}/site-assets',
        'models':len(results['outfits']),'artwork':len(artwork)}
    (ROOT/'references/runtime-assets.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(json.dumps(record),flush=True)


if __name__=='__main__':run()
