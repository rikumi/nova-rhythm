"""Bring unusually flat/deep scenes into a bounded parallax range without repainting."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/layering'))
from run_batch import read,write
from export_scene import export


def apply(minimum=.35,maximum=1.25,publish=False):
    runtime=ROOT/'.build/sharp-layering';batch=runtime/'batch'
    results=read(batch/'results.json');previous=read(ROOT/'references/sharp-scenes-depth.json')
    rules={'schemaVersion':1,'measure':'focus_distance * (1 / depth_p01 - 1 / depth_p99)',
        'minimum':minimum,'maximum':maximum,'outfits':{}}
    manual={'1001','1003','1007','1008'}
    counts={'expanded':0,'compressed':0,'manual':0,'unchanged':0}
    for code,result in results.items():
        old=result.get('depth_compression',{})
        percentiles=np.asarray(old.get('original_depth_percentiles',result['depth_percentiles']))
        focus=old.get('focus_anchor',result['focus_distance'])
        span=float(focus*(1/percentiles[0]-1/percentiles[2]))
        rule=None
        if code in manual:
            rule={key:value for key,value in previous['outfits'][code].items() if key not in ['method','source_prediction_sha256']}
            rule['target_relative_inverse_depth_span']=min(maximum,max(minimum,span*rule['scale']))
            counts['manual']+=1
        elif span<minimum:
            logarithm=np.log(percentiles/focus);bound=np.log(20.)
            def transformed_span(exponent):
                depth=focus*np.exp(np.clip(exponent*logarithm,-bound,bound))
                return float(focus*(1/depth[0]-1/depth[2]))
            lo=1.;hi=2.
            while transformed_span(hi)<minimum and hi<128:hi*=2
            if transformed_span(hi)<minimum:raise RuntimeError(f'{code}: depth is too uniform to expand safely')
            for _ in range(50):
                mid=(lo+hi)/2
                if transformed_span(mid)<minimum:lo=mid
                else:hi=mid
            rule={'name':result['name'],'exponent':(lo+hi)/2,'original_relative_inverse_depth_span':span,
                'target_relative_inverse_depth_span':minimum}
            counts['expanded']+=1
        elif span>maximum:
            rule={'name':result['name'],'scale':maximum/span,'original_relative_inverse_depth_span':span,
                'target_relative_inverse_depth_span':maximum}
            counts['compressed']+=1
        else:counts['unchanged']+=1
        if rule:
            rule['source_prediction_sha256']=result['source_prediction_sha256'];rules['outfits'][code]=rule
    write(ROOT/'references/sharp-scenes-depth.json',rules)
    print('Depth corrections:',counts,flush=True)
    for code in rules['outfits']:
        updated=export(code,runtime,quiet=True);results[code].update(updated)
        print('Adjusted',code,results[code]['name'],updated['depth_compression']['relative_inverse_depth_span'],flush=True)
    for code,result in results.items():
        span=result['focus_distance']*(1/result['depth_percentiles'][0]-1/result['depth_percentiles'][2])
        # Explicit semantic edits (e.g. aligning a swim ring with the water) take
        # precedence over the generic minimum; never expand those scenes again.
        if not result.get('semantic_depth') and not minimum-1e-6<=span<=maximum+1e-6:
            raise RuntimeError(f'{code}: corrected depth span out of bounds: {span}')
    write(batch/'results.json',results)
    plan=read(ROOT/'references/sharp-scenes-plan.json');plan['depth_overrides']=rules;write(ROOT/'references/sharp-scenes-plan.json',plan)
    if publish:
        from publish_scenes import publish as upload
        upload(runtime,plan,results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--minimum',type=float,default=.35);parser.add_argument('--maximum',type=float,default=1.25)
    parser.add_argument('--publish',action='store_true');args=parser.parse_args();apply(args.minimum,args.maximum,args.publish)
