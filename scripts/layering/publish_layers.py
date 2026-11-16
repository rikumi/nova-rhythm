"""Upload completed semantic layers to a separate Release, then deploy only its manifests."""
import datetime
import json
import shutil
import shlex
import subprocess
import time
from pathlib import Path

from run_batch import ROOT,card_for_result,digest,write,read,review_for_result

def approved_batch(batch,reviews):
    from types import SimpleNamespace
    approved={code:result for code,result in batch.completed.items()
              if review_for_result(result,reviews.get(code)).get('status')=='accepted'}
    if not approved:raise RuntimeError('No hash-matched accepted outfits to publish')
    return SimpleNamespace(batch=batch.batch,runtime=batch.runtime,completed=approved,
        plan={**batch.plan,'items':[item for item in batch.plan['items'] if item['code'] in approved]})


def publish(batch, approved_only=False):
    if approved_only:
        review_path=ROOT/'references/experimental-layering-reviews.json'
        batch=approved_batch(batch,read(review_path).get('items',{}))
    hold=batch.batch/'publication-hold.json'
    publication=getattr(batch,'plan',{}).get('publication',{})
    if not approved_only and (hold.exists() or publication.get('enabled') is False):
        reason=read(hold).get('reason','Awaiting review') if hold.exists() else publication.get('reason','Awaiting review')
        write(batch.batch/'publication.json',{'state':'held','reason':reason})
        print('Publication held: no release upload, push or deployment will run.',flush=True)
        return False
    from PIL import Image
    import numpy as np
    if len(batch.completed)!=len(batch.plan['items']):raise RuntimeError('All planned outfits must finish before publication')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if branch!='main':raise RuntimeError('Publication requires main; generated results are retained for a later retry')
    gh=shutil.which('gh') or str(ROOT/'tools/github-cli/portable/bin/gh.exe')
    repository='rikumi/nova-rhythm'
    date=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d')
    tag='experimental-layering-qwen-'+('reviewed-' if approved_only else '')+date
    output=batch.batch/('reviewed-release-assets' if approved_only else 'release-assets');output.mkdir(exist_ok=True)
    def cli(*arguments,check=True):
        result=subprocess.run([gh,*map(str,arguments)],cwd=ROOT,text=True,encoding='utf8',capture_output=True)
        if check and result.returncode:raise RuntimeError(result.stderr)
        return result
    assets=[];cards={};details={};reviews={}
    review_file=ROOT/'references/experimental-layering-reviews.json'
    requested_reviews=read(review_file).get('items',{}) if review_file.exists() else {}
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
        reviews[code]=review_for_result(result,requested_reviews.get(code))
    manifest={'schemaVersion':1,'model':'Qwen-Image-Layered','releaseUrl':f'https://github.com/{repository}/releases/tag/{tag}',
              'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'outfits':cards,'reviews':reviews}
    write(output/'experimental-layering.json',manifest)
    write(output/'generation-results.json',{'schemaVersion':1,'settings':batch.plan,'results':details})
    for name in ['experimental-layering.json','generation-results.json']:
        file=output/name;assets.append({'path':str(file),'name':name,'sha256':digest(file),'size':file.stat().st_size})
    write(batch.batch/('reviewed-release-assets.json' if approved_only else 'release-assets.json'),assets)
    notes=batch.batch/'release-notes.txt'
    notes.write_text('Qwen-Image-Layered semantic artwork decomposition experiment.\n\n'
        f'{len(cards)} static outfits, 2–10 nonempty RGBA layers per outfit (normally at least four). '
        'PNG outputs are encoded as lossless WebP and verified pixel-for-pixel. '
        'Original artwork is preserved in the artwork release.\n\n'
        'The website enables these assets with the persistent AI layering checkbox or experimental_layering=1. '
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
    # Tag lookup omits draft releases; list authenticated releases to find the draft ID.
    release_pages=json.loads(cli('api',f'repos/{repository}/releases?per_page=100','--paginate','--slurp').stdout)
    release=next(entry for page in release_pages for entry in page if entry['tag_name']==tag)
    pages=json.loads(cli('api',f'repos/{repository}/releases/{release["id"]}/assets?per_page=100','--paginate','--slurp').stdout)
    remote={asset['name']:asset for page in pages for asset in page}
    for asset in assets:
        stored=remote.get(asset['name'],{})
        if stored.get('size')!=asset['size'] or stored.get('digest')!='sha256:'+asset['sha256']:
            raise RuntimeError('Release asset verification failed: '+asset['name'])
    if approved_only:
        current_reviews=read(ROOT/'references/experimental-layering-reviews.json').get('items',{})
        still_approved=approved_batch(batch,current_reviews)
        if set(still_approved.completed)!=set(batch.completed):raise RuntimeError('Acceptance changed during upload; deployment withheld')
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


if __name__=='__main__':
    import argparse
    from run_batch import Batch
    parser=argparse.ArgumentParser()
    parser.add_argument('--approved-only',action='store_true',required=True)
    parser.add_argument('--runtime',default=str(ROOT/'.build/layering-trial'))
    parser.add_argument('--plan',default=str(ROOT/'references/experimental-layering-plan.json'))
    args=parser.parse_args();args.port=8189
    batch=Batch(args)
    reviews=read(ROOT/'references/experimental-layering-reviews.json').get('items',{})
    for item in batch.plan['items']:
        if reviews.get(item['code'],{}).get('status')!='accepted':continue
        source=batch.runtime/item['code']/'original.png'
        result=batch.valid_result(item,digest(source))
        if result:batch.completed[item['code']]=result
    publish(batch,approved_only=True)
