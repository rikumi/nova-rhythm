"""Restore visible layer detail from original pixels; preserve generated occluded fills."""
import argparse
import copy
import shutil
import time
from pathlib import Path

from run_batch import ROOT, read, write, digest, card_for_result


def guided_alpha(rgb, alpha, radius=8, epsilon=.001):
    import numpy as np
    from scipy.ndimage import uniform_filter, minimum_filter
    def box(value):
        return uniform_filter(value, size=radius*2+1, mode='reflect')
    channels=[rgb[:,:,c] for c in range(3)]
    means=[box(channel) for channel in channels]
    covariance={(i,j):box(channels[i]*channels[j])-means[i]*means[j]
                for i in range(3) for j in range(i,3)}
    a,b,c=covariance[0,0]+epsilon,covariance[0,1],covariance[0,2]
    d,e,f=covariance[1,1]+epsilon,covariance[1,2],covariance[2,2]+epsilon
    determinant=np.maximum(a*(d*f-e*e)-b*(b*f-c*e)+c*(b*e-c*d),1e-12)
    inverse=[(d*f-e*e)/determinant,(c*e-b*f)/determinant,(b*e-c*d)/determinant,
             (a*f-c*c)/determinant,(b*c-a*e)/determinant,(a*d-b*b)/determinant]
    mean_alpha=box(alpha)
    cross=[box(channels[i]*alpha)-means[i]*mean_alpha for i in range(3)]
    coefficients=[inverse[0]*cross[0]+inverse[1]*cross[1]+inverse[2]*cross[2],
                  inverse[1]*cross[0]+inverse[3]*cross[1]+inverse[4]*cross[2],
                  inverse[2]*cross[0]+inverse[4]*cross[1]+inverse[5]*cross[2]]
    offset=mean_alpha-sum(coefficients[i]*means[i] for i in range(3))
    refined=np.clip(sum(box(coefficients[i])*channels[i] for i in range(3))+box(offset),0,1)
    # Refine only the boundary; lock certain interiors and distant transparent regions.
    sure_foreground=minimum_filter(alpha>.995,size=7)
    sure_background=minimum_filter(alpha<.005,size=7)
    refined[sure_foreground]=1
    refined[sure_background]=0
    return np.rint(refined*255).astype(np.uint8)


def backfill(code, runtime, output):
    import numpy as np
    from PIL import Image
    started=time.monotonic()
    folder=runtime/code
    result=read(folder/'result.json')
    original=Image.open(folder/'original.png').convert('RGB')
    size=original.size
    source=np.asarray(original,dtype=np.float32)/255
    colors=[];alphas=[]
    for index,entry in enumerate(result['layers']):
        path=folder/entry['file']
        if digest(path)!=entry['sha256']:raise RuntimeError('Layer hash mismatch: '+str(path))
        image=Image.open(path).convert('RGBA')
        # Resize channels separately: transparent RGB contains the occluded paint.
        colors.append(np.asarray(image.convert('RGB').resize(size,Image.Resampling.LANCZOS),dtype=np.float32)/255)
        alpha=np.asarray(image.getchannel('A').resize(size,Image.Resampling.BICUBIC),dtype=np.float32)/255
        # The original canvas is opaque; eliminate small diffusion alpha holes
        # in its backing while keeping foreground transparency and occluded paint.
        refined=np.full(alpha.shape,255,dtype=np.uint8) if index==0 else guided_alpha(source,alpha)
        alphas.append(refined.astype(np.float32)/255)

    def composite():
        image=np.zeros_like(source)
        for rgb,alpha in zip(colors,alphas):image=rgb*alpha[:,:,None]+image*(1-alpha[:,:,None])
        return image

    # Visibility weights distinguish visible original surfaces from hidden AI paint.
    weights=[None]*len(alphas)
    transmission=np.ones(source.shape[:2],dtype=np.float32)
    for index in range(len(alphas)-1,-1,-1):
        weights[index]=alphas[index]*transmission
        transmission*=1-alphas[index]
    if float(transmission.max())>.001:raise RuntimeError('Layers lack an opaque backing; cannot preserve the original composite')
    owner=np.argmax(np.stack(weights),axis=0)
    residual=source-composite()
    for index,weight in enumerate(weights):
        selected=owner==index
        correction=residual/np.maximum(weight[:,:,None],1e-6)
        colors[index][selected]=np.clip(colors[index][selected]+correction[selected],0,1)

    # Unmixing can clip at antialiased edges. Use original colors on the visible
    # surfaces of those edge pixels; fully occluded background paint stays untouched.
    unresolved=np.max(np.abs(source-composite()),axis=2)>1/510
    for index,weight in enumerate(weights):
        selected=unresolved & (weight>1e-5)
        colors[index][selected]=source[selected]

    target=output/code;target.mkdir(parents=True,exist_ok=True)
    shutil.copy2(folder/'original.png',target/'original.png')
    generated=[]
    decoded=[]
    for index,(rgb,alpha,entry) in enumerate(zip(colors,alphas,result['layers'])):
        array=np.dstack([np.rint(np.clip(rgb,0,1)*255).astype(np.uint8),np.rint(alpha*255).astype(np.uint8)])
        image=Image.fromarray(array);path=target/entry['file'];image.save(path)
        generated.append({**entry,'size':list(size),'sha256':digest(path)})
        decoded.append(image)
    reconstruction=Image.new('RGBA',size)
    for image in decoded:reconstruction.alpha_composite(image)
    reconstructed=np.asarray(reconstruction.convert('RGB'),dtype=np.float32)
    error=np.abs(reconstructed-np.asarray(original,dtype=np.float32))
    rmse=float(np.sqrt(np.mean(error*error)))
    psnr=float(20*np.log10(255/max(rmse,1e-8)))
    metrics={'width':size[0],'height':size[1],'mean_absolute_error':float(error.mean()),
             'max_error':int(error.max()),'psnr_db':psnr,'channels_within_one':float((error<=1).mean()),
             'exact_pixels':float(np.all(error==0,axis=2).mean()),'elapsed_seconds':round(time.monotonic()-started,1)}
    if psnr<48 or metrics['channels_within_one']<.995:
        raise RuntimeError('Original-pixel reconstruction check failed: '+str(metrics))
    reconstruction.save(target/'reconstructed.png')
    updated=copy.deepcopy(result)
    updated.update(input_size=list(size),layers=generated)
    updated['hd_backfill']={'method':'original-pixel-visibility-backfill-v1','original_size':list(size),
        'mask_generation_size':result['input_size'],'source_sha256':digest(folder/'original.png'),
        'mask_layer_hashes':{entry['file']:entry['sha256'] for entry in result['layers']},
        'hidden_regions':'Generated occluded paint is interpolated; it is not original high-resolution artwork.',
        'metrics':metrics}
    write(target/'result.json',updated)
    overrides_path=output/'local-overrides.json'
    overrides=read(overrides_path) if overrides_path.exists() else {}
    overrides[code]=card_for_result(code,updated,f'/__layering-hd/{code}/')
    write(overrides_path,overrides)
    print(code,metrics,flush=True)
    return updated


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--codes',nargs='+',default=['4016','4027','4043'])
    parser.add_argument('--runtime',type=Path,default=ROOT/'.build/layering-trial')
    parser.add_argument('--output',type=Path,default=ROOT/'.build/layering-hd')
    args=parser.parse_args()
    for code in args.codes:backfill(code,args.runtime,args.output)
