"""Publish verified lossless depth packages on site-assets, then prepare web metadata."""
import argparse
import json
from pathlib import Path
import shutil

from export_depth_layers import ROOT,RUNTIME,read,write,sha
from store_repository_assets import WORK,GH,REPOSITORY,git,push,command


def publish(partial=False):
    if git('branch','--show-current')!='site-assets' or git('status','--porcelain'):
        raise RuntimeError('Expected a clean isolated site-assets worktree')
    scenes=read(ROOT/'public/data/sharp-scenes.json')
    pending=[]
    exported={}
    for code,scene in scenes['outfits'].items():
        folder=RUNTIME/code
        if partial and not (folder/'layers.json').exists():continue
        report=read(folder/'layers.json')
        if report['source_scene_sha256']!=scene['scene_sha256'] or len(report['layers'])!=20:
            raise ValueError(f'{code}: scene or layer count mismatch')
        source=folder/'scene.layers'
        if source.stat().st_size!=report['bytes'] or sha(source)!=report['sha256']:
            raise ValueError(f'{code}: package hash mismatch')
        if report['bytes']>=100*1024**2 or report['front_comparison']['mean_absolute_error_255']>1:
            raise ValueError(f'{code}: package exceeds publication limits')
        path=f'depth-layers/{code}-{report["sha256"][:12]}.layers'
        target=WORK/path;target.parent.mkdir(exist_ok=True)
        if not target.exists():shutil.copyfile(source,target)
        if sha(target)!=report['sha256']:raise ValueError(f'{code}: copy hash mismatch')
        if not git('ls-files','--',path):pending.append(path)
        exported[code]={**report,'path':path}
    for start in range(0,len(pending),12):
        paths=pending[start:start+12]
        git('add','--',*paths);git('commit','-m',f'Version mobile depth-layer packages {start+1}-{start+len(paths)}')
        push()
    if partial:
        print(json.dumps({'uploaded':len(exported),'remaining':len(scenes['outfits'])-len(exported)}),flush=True)
        return
    manifest=read(WORK/'manifest.json');manifest['depth_layers']=exported
    write(WORK/'manifest.json',manifest)
    git('add','--','manifest.json')
    if git('status','--porcelain'):git('commit','-m','Record verified twenty-layer mobile scenes')
    push();revision=git('rev-parse','HEAD')
    remote=json.loads(command(GH,'api',f'repos/{REPOSITORY}/git/trees/{revision}?recursive=1'))
    actual={item['path']:(item['sha'],item['size']) for item in remote['tree'] if item['type']=='blob'}
    for code,report in exported.items():
        blob=git('rev-parse',f'{revision}:{report["path"]}')
        if actual.get(report['path'])!=(blob,report['bytes']):raise ValueError(f'{code}: remote object mismatch')
    assets=read(ROOT/'references/runtime-assets.json');assets['commit']=revision;assets['depth_layer_models']=len(exported)
    write(ROOT/'references/runtime-assets.json',assets)
    write(ROOT/'references/sharp-depth-layers-results.json',{'schemaVersion':1,'publication':{'verified':True,'asset_commit':revision},'outfits':exported})
    # prepare_web also retains this mapping on subsequent original-model rebuilds.
    from prepare_web import prepare
    prepare()
    print(json.dumps({'published':len(exported),'bytes':sum(r['bytes'] for r in exported.values()),'commit':revision}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true')
    publish(parser.parse_args().partial)
