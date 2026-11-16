"""Upload completed semantic layers to a separate Release, then deploy only its manifests."""
import datetime
import json
import shutil
import shlex
import subprocess
import time
from pathlib import Path

from run_batch import ROOT,card_for_result,digest,write

def publish(batch):
    from PIL import Image
    import numpy as np
    if len(batch.completed)!=len(batch.plan['items']):raise RuntimeError('All planned outfits must finish before publication')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if branch!='main':raise RuntimeError('Publication requires main; generated results are retained for a later retry')
    gh=shutil.which('gh') or str(ROOT/'tools/github-cli/portable/bin/gh.exe')
    repository='rikumi/nova-rhythm'
    date=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d')
    tag='experimental-layering-qwen-'+date
    output=batch.batch/'release-assets';output.mkdir(exist_ok=True)
    def cli(*arguments,check=True):
        result=subprocess.run([gh,*map(str,arguments)],cwd=ROOT,text=True,encoding='utf8',capture_output=True)
        if check and result.returncode:raise RuntimeError(result.stderr)
        return result
    assets=[];cards={};details={}
    for item in batch.plan['items']:
        code=item['code'];result=batch.completed[code]
        card=card_for_result(code,result,'')
        for entry,layer in zip(result['layers'],card['layers']):
            source=batch.runtime/code/entry['file']
            temporary=output/f'{code}-{source.stem}.webp'
            with Image.open(source) as image:image.save(temporary,lossless=True,quality=100,method=6,exact=True)
            with Image.open(source) as before,Image.open(temporary) as after:
                if not np.array_equal(np.asarray(before.convert('RGBA')),np.asarray(after.convert('RGBA'))):
                    raise RuntimeError('Lossless export changed RGBA pixels: '+str(source))
            sha=digest(temporary)
            target=output/f'{code}-{source.stem}-{sha[:12]}.webp'
            if target!=temporary:temporary.replace(target)
            layer['path']=f'https://github.com/{repository}/releases/download/{tag}/{target.name}'
            assets.append({'path':str(target),'name':target.name,'sha256':sha,'size':target.stat().st_size})
        cards[code]=card
        details[code]={key:value for key,value in result.items() if key not in ('history','folder')}
    manifest={'schemaVersion':1,'model':'Qwen-Image-Layered','releaseUrl':f'https://github.com/{repository}/releases/tag/{tag}',
              'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'outfits':cards}
    write(output/'experimental-layering.json',manifest)
    write(output/'generation-results.json',{'schemaVersion':1,'settings':batch.plan,'results':details})
    for name in ['experimental-layering.json','generation-results.json']:
        file=output/name;assets.append({'path':str(file),'name':name,'sha256':digest(file),'size':file.stat().st_size})
    write(batch.batch/'release-assets.json',assets)
    notes=batch.batch/'release-notes.txt'
    notes.write_text('Qwen-Image-Layered semantic artwork decomposition experiment.\n\n'
        f'{len(cards)} static outfits, 4–10 nonempty RGBA layers per outfit. '
        'PNG outputs are encoded as lossless WebP and verified pixel-for-pixel. '
        'Original artwork is preserved in the artwork release.\n\n'
        'The website enables these assets only with experimental_layering=1. '
        'Generated layers may contain model artifacts; these are experimental assets, not original game layers.\n\n'
        'Model: https://github.com/QwenLM/Qwen-Image-Layered\n'
        'Game artwork copyright remains with its respective rights holders.\n',encoding='utf8')
    existing=cli('release','view',tag,'--repo',repository,'--json','id',check=False)
    if existing.returncode:
        cli('release','create',tag,'--repo',repository,'--target','main','--draft',
            '--title','Experimental Qwen layered artwork '+date,'--notes-file',notes)
    for start in range(0,len(assets),15):
        files=[asset['path'] for asset in assets[start:start+15]]
        for attempt in range(4):
            result=cli('release','upload',tag,*files,'--repo',repository,'--clobber',check=False)
            if not result.returncode:break
            if attempt==3:raise RuntimeError(result.stderr)
            time.sleep(10*(attempt+1))
        print('Uploaded',min(start+15,len(assets)),'/',len(assets),'assets',flush=True)
    release=json.loads(cli('api',f'repos/{repository}/releases/tags/{tag}').stdout)
    pages=json.loads(cli('api',f'repos/{repository}/releases/{release["id"]}/assets?per_page=100','--paginate','--slurp').stdout)
    remote={asset['name']:asset for page in pages for asset in page}
    for asset in assets:
        stored=remote.get(asset['name'],{})
        if stored.get('size')!=asset['size'] or stored.get('digest')!='sha256:'+asset['sha256']:
            raise RuntimeError('Release asset verification failed: '+asset['name'])
    cli('release','edit',tag,'--repo',repository,'--draft=false','--latest=false')
    # Only these generated files are committed, preserving concurrent CSS/JSON work.
    public=ROOT/'public/data/experimental-layering.json'
    reference=ROOT/'references/experimental-layering-results.json'
    write(public,manifest)
    write(reference,{'schemaVersion':1,'releaseUrl':manifest['releaseUrl'],'results':details})
    paths=['public/data/experimental-layering.json','references/experimental-layering-results.json']
    subprocess.run(['git','add','--',*paths],cwd=ROOT,check=True)
    subprocess.run(['git','commit','--only','-m','Publish experimental Qwen layers for static outfits','--',*paths],cwd=ROOT,check=True)
    helper='!'+shlex.quote(str(Path(gh).resolve()).replace('\\','/'))+' auth git-credential'
    subprocess.run(['git','-c','credential.helper=','-c','credential.helper='+helper,'push','origin','main'],cwd=ROOT,check=True)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    write(batch.batch/'publication.json',{'tag':tag,'releaseUrl':manifest['releaseUrl'],'commit':sha,'asset_count':len(assets),'verified':True})
    # Wait for the matching Pages run, leaving a concrete result if deployment fails.
    for attempt in range(240):
        runs=json.loads(cli('run','list','--repo',repository,'--commit',sha,'--limit','5','--json','databaseId,status,conclusion,url').stdout)
        if runs:
            run=runs[0]
            write(batch.batch/'deployment.json',run)
            if run['status']=='completed':
                if run['conclusion']!='success':raise RuntimeError('Pages deployment failed: '+run['url'])
                return
        time.sleep(15)
    raise RuntimeError('Pages deployment did not finish within one hour')
