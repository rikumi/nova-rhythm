"""Generate all static outfit Gaussian scenes locally; never pushes or deploys the site."""
import argparse
import ctypes
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/layering'))
from run_batch import digest,read,write
from export_scene import export


def run(args):
    import numpy as np
    from PIL import Image
    runtime=Path(args.runtime);batch=runtime/'batch';batch.mkdir(parents=True,exist_ok=True)
    checkpoint=runtime/'sharp_2572gikvuh.pt'
    checkpoint_hash=digest(checkpoint)
    source_revision=digest(runtime/'ml-sharp/src/sharp/models/predictor.py')
    originals=ROOT/'.build/layering-trial'
    items=[]
    for outfit in read(ROOT/'public/data/outfits.json')['items']:
        if outfit['card']['layers']:continue
        code=outfit['code'];source=originals/code/'original.png';source.parent.mkdir(exist_ok=True)
        source_url=outfit['staticImage']
        if not source.exists():
            with urllib.request.urlopen(source_url,timeout=90) as response:source.write_bytes(response.read())
        with Image.open(source) as image:size=list(image.size)
        items.append({'code':code,'outfit_id':outfit['id'],'name':outfit['name'],'source_url':source_url,
            'source_sha256':digest(source),'source_size':size})
    items.sort(key=lambda item:(item['code'] not in ['4016','4027','4043'],item['code']))
    settings={'model':'apple/Sharp','checkpoint_sha256':checkpoint_hash,'predictor_source_sha256':source_revision,
        'internal_size':[1536,1536],'focal_length_mm':30,'precision':'autocast bfloat16','export':'metric-covariance-v1'}
    plan={'schemaVersion':1,'settings':settings,'items':items}
    override_file=ROOT/'references/sharp-scenes-depth.json'
    if override_file.exists():plan['depth_overrides']=read(override_file)
    semantic_file=ROOT/'references/sharp-scenes-semantic.json'
    if semantic_file.exists():plan['semantic_overrides']=read(semantic_file)
    write(ROOT/'references/sharp-scenes-plan.json',plan)
    completed={};failures={};started=time.time()
    def status(phase,current=None,**extra):
        data={'state':'running','phase':phase,'current':current,'completed':len(completed),'total':len(items),
            'failed':failures,'started_at':started,'updated_at':time.time(),**extra}
        write(batch/'status.json',data);print(json.dumps(data,ensure_ascii=True),flush=True)
    status('checking-cache')
    model=None;torch=None
    try:
        if os.name=='nt':ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        for item in items:
            code=item['code'];folder=runtime/code;folder.mkdir(exist_ok=True)
            fingerprint=hashlib.sha256(json.dumps({'settings':settings,'source_sha256':item['source_sha256']},sort_keys=True).encode()).hexdigest()
            status('checking-scene',{'code':code,'name':item['name']})
            try:
                prediction_path=folder/'prediction.json';cloud=folder/'gaussians.npz';metadata=folder/'scene.json';ply=folder/'scene.ply'
                prediction=read(prediction_path) if prediction_path.exists() else {}
                valid=cloud.exists() and prediction.get('input_size')==item['source_size'] and prediction.get('model')=='apple/Sharp'
                if valid and prediction.get('fingerprint') not in (None,fingerprint):valid=False
                if valid:
                    with np.load(cloud) as values:
                        valid=all(np.isfinite(value).all() for value in values.values())
                        valid=valid and len(values['mean_vectors'])==prediction['gaussian_count']
                    if not prediction.get('fingerprint'):
                        prediction.update(fingerprint=fingerprint,source_sha256=item['source_sha256'],checkpoint_sha256=checkpoint_hash,
                            adopted_cached_trial=True);write(prediction_path,prediction)
                if not valid:
                    if model is None:
                        status('loading-model',{'code':code,'name':item['name']})
                        sys.path.insert(0,str(runtime/'ml-sharp/src'))
                        import torch as torch_module
                        from sharp.models import PredictorParams,create_predictor
                        torch=torch_module;torch.set_float32_matmul_precision('high')
                        model=create_predictor(PredictorParams())
                        weights=torch.load(checkpoint,map_location='cpu',mmap=True,weights_only=True)
                        model.load_state_dict(weights,assign=True);del weights
                        model.eval().to('cuda');gc.collect()
                    status('inference',{'code':code,'name':item['name']})
                    with Image.open(originals/code/'original.png') as image:rgb=np.asarray(image.convert('RGB'))
                    height,width=rgb.shape[:2];focal=30*math.hypot(width,height)/math.hypot(36,24)
                    image=torch.from_numpy(rgb.copy()).float().cuda().permute(2,0,1)/255
                    image=torch.nn.functional.interpolate(image[None],(1536,1536),mode='bilinear',align_corners=True)
                    factor=torch.tensor([focal/width],dtype=torch.float32,device='cuda')
                    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();begin=time.monotonic()
                    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):gaussians=model(image,factor)
                    torch.cuda.synchronize();elapsed=time.monotonic()-begin
                    values={name:value.detach().float().cpu().numpy()[0] for name,value in zip(gaussians._fields,gaussians)}
                    if not all(np.isfinite(value).all() for value in values.values()):raise RuntimeError('Non-finite Gaussian output')
                    temporary=folder/'gaussians.npz.tmp'
                    with temporary.open('wb') as stream:np.savez_compressed(stream,**values)
                    temporary.replace(cloud)
                    prediction={'model':'apple/Sharp','code':code,'input_size':[width,height],'internal_size':[1536,1536],
                        'focal_length_px':focal,'inference_seconds':round(elapsed,3),'precision':settings['precision'],
                        'gaussian_count':len(values['mean_vectors']),'peak_gpu_allocated_gb':round(torch.cuda.max_memory_allocated()/1e9,3),
                        'gaussians_coordinate_system':'SHARP NDC camera coordinates, before metric unprojection',
                        'fingerprint':fingerprint,'source_sha256':item['source_sha256'],'checkpoint_sha256':checkpoint_hash}
                    write(prediction_path,prediction)
                    del image,factor,gaussians,values;torch.cuda.empty_cache()
                existing=read(metadata) if metadata.exists() else {}
                override_file=ROOT/'references/sharp-scenes-depth.json'
                override=read(override_file).get('outfits',{}).get(code,{}) if override_file.exists() else {}
                semantic=read(semantic_file).get('outfits',{}).get(code,{}) if semantic_file.exists() else {}
                if (not ply.exists() or existing.get('fingerprint')!=fingerprint or existing.get('scene_sha256')!=digest(ply)
                        or existing.get('depth_override',{})!=override or existing.get('semantic_depth',{})!=semantic):
                    status('export',{'code':code,'name':item['name']});existing=export(code,runtime,quiet=True)
                completed[code]={**existing,'name':item['name'],'outfit_id':item['outfit_id'],'source_url':item['source_url']}
                write(batch/'results.json',completed);status('scene-complete',{'code':code,'name':item['name']})
            except Exception:
                failures[code]=traceback.format_exc();write(folder/'error.json',{'traceback':failures[code]});status('scene-failed',{'code':code,'name':item['name']})
        if model is not None:
            del model;gc.collect();torch.cuda.empty_cache()
        if failures:raise RuntimeError(f'{len(failures)} scenes failed; release publication withheld')
        status('generation-complete')
        if args.publish:
            from publish_scenes import publish
            status('publishing');publish(runtime,plan,completed)
        status('complete',state='complete')
    except Exception:
        status('failed',state='failed',error=traceback.format_exc());raise
    finally:
        if os.name=='nt':ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,default=ROOT/'.build/sharp-layering')
    parser.add_argument('--publish',action='store_true');run(parser.parse_args())
