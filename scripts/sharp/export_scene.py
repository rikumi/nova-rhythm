"""Export cached SHARP predictions as metric 3D Gaussians, without depth slicing."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/layering'))
from run_batch import digest,write,read


def metric_gaussians(means,scales,quaternions,axis_scale,depth_scale=1.,focus=None,depth_exponent=1.):
    """Apply camera unprojection to centers AND full oriented covariance."""
    rotation=Rotation.from_quat(quaternions[:,[1,2,3,0]]).as_matrix()
    basis=rotation*scales[:,None,:]
    basis*=axis_scale[None,:,None]
    positions=means*axis_scale
    if depth_scale!=1:
        if not 0<depth_scale<=1 or not focus or focus<=0:raise ValueError('Invalid inverse-depth compression')
        a=(1-depth_scale)/focus;s=1/(a*positions[:,2]+depth_scale)
        jacobian=np.zeros_like(basis)
        jacobian[:,0,0]=s;jacobian[:,1,1]=s;jacobian[:,2,2]=depth_scale*s*s
        jacobian[:,0,2]=-a*s*s*positions[:,0];jacobian[:,1,2]=-a*s*s*positions[:,1]
        basis=jacobian@basis
        positions=positions*s[:,None]
    elif depth_exponent!=1:
        if depth_exponent<=0 or not focus or focus<=0:raise ValueError('Invalid log-depth expansion')
        z=positions[:,2];log_depth=depth_exponent*np.log(z/focus);bound=np.log(20.)
        new_z=focus*np.exp(np.clip(log_depth,-bound,bound));s=new_z/z
        derivative=np.where(np.abs(log_depth)<bound,depth_exponent*s,0.)
        rate=(derivative-s)/z
        jacobian=np.zeros_like(basis)
        jacobian[:,0,0]=s;jacobian[:,1,1]=s;jacobian[:,2,2]=derivative
        jacobian[:,0,2]=positions[:,0]*rate;jacobian[:,1,2]=positions[:,1]*rate
        basis=jacobian@basis;positions=positions*s[:,None]
    covariance=basis@basis.transpose(0,2,1)
    eigenvalues,eigenvectors=np.linalg.eigh(covariance)
    eigenvectors[:,:,2]*=np.where(np.linalg.det(eigenvectors)<0,-1,1)[:,None]
    q=Rotation.from_matrix(eigenvectors).as_quat()[:,[3,0,1,2]]
    return positions,np.sqrt(np.maximum(eigenvalues,1e-16)),q


def semantic_warp(positions,scales,quaternions,weights,weight_gradient,focus,settings):
    """Ray-preserving spatial depth warp, including the selection gradient in covariance."""
    rotation=Rotation.from_quat(quaternions[:,[1,2,3,0]]).as_matrix()
    basis=rotation*scales[:,None,:]
    foreground=settings['foreground_depth'];background=settings['background_depth']
    fg_detail=settings['foreground_detail_scale'];bg_detail=settings['background_detail_scale']
    z=positions[:,2]
    detail=bg_detail+(fg_detail-bg_detail)*weights
    offset=focus*((background-bg_detail)+weights*((foreground-fg_detail)-(background-bg_detail)))
    new_z=detail*z+offset;s=new_z/z
    response=(fg_detail-bg_detail)*z+focus*((foreground-fg_detail)-(background-bg_detail))
    gradient=response[:,None]*weight_gradient
    gradient[:,2]+=detail
    gradient/=z[:,None];gradient[:,2]-=new_z/(z*z)
    jacobian=positions[:,:,None]*gradient[:,None,:]
    jacobian[:,0,0]+=s;jacobian[:,1,1]+=s;jacobian[:,2,2]+=s
    basis=jacobian@basis;covariance=basis@basis.transpose(0,2,1)
    eigenvalues,eigenvectors=np.linalg.eigh(covariance)
    eigenvectors[:,:,2]*=np.where(np.linalg.det(eigenvectors)<0,-1,1)[:,None]
    q=Rotation.from_matrix(eigenvectors).as_quat()[:,[3,0,1,2]]
    return positions*s[:,None],np.sqrt(np.maximum(eigenvalues,1e-16)),q


def export(code='4016',runtime=None,quiet=False):
    folder=(Path(runtime) if runtime else ROOT/'.build/sharp-layering')/code
    prediction=json.loads((folder/'prediction.json').read_text(encoding='utf8'))
    override_file=ROOT/'references/sharp-scenes-depth.json'
    override=read(override_file).get('outfits',{}).get(code,{}) if override_file.exists() else {}
    depth_scale=override.get('scale',1.)
    depth_exponent=override.get('exponent',1.)
    semantic_file=ROOT/'references/sharp-scenes-semantic.json'
    semantic=read(semantic_file).get('outfits',{}).get(code,{}) if semantic_file.exists() else {}
    selection=None
    if semantic:
        from PIL import Image,ImageDraw,ImageFilter
        mask_width=1024;mask_height=round(mask_width*prediction['input_size'][1]/prediction['input_size'][0])
        mask=Image.new('L',(mask_width,mask_height));draw=ImageDraw.Draw(mask)
        for polygon in semantic['polygons']:draw.polygon([(x*mask_width,y*mask_height) for x,y in polygon],fill=255)
        mask=mask.filter(ImageFilter.GaussianBlur(semantic['feather']*min(mask_width,mask_height)))
        mask.save(folder/'semantic-mask.png');selection=np.asarray(mask,dtype=float)/255
        gradient_v,gradient_u=np.gradient(selection);gradient_u*=mask_width;gradient_v*=mask_height
    width,height=prediction['input_size'];focal=prediction['focal_length_px']
    axis_scale=np.array([width/(2*focal),height/(2*focal),1],dtype=np.float64)
    with np.load(folder/'gaussians.npz') as data:
        means=data['mean_vectors'];original_scales=data['singular_values'];quaternions=data['quaternions']
        original_colors=data['colors'];opacities=data['opacities'].reshape(-1)
        count=len(means)
        z=means[:,2];visible=(opacities>.1)&(z>0)
        focus=float(np.median(z[visible]))
        original_focus=focus
        original_depth_percentiles=np.quantile(z[visible],[.01,.5,.99])
        attributes=np.empty((count,14),dtype='<f4')
        for start in range(0,count,65536):
            stop=min(start+65536,count)
            xyz,scales,q=metric_gaussians(means[start:stop],original_scales[start:stop],quaternions[start:stop],axis_scale,depth_scale,focus,depth_exponent)
            if semantic:
                from scipy.ndimage import map_coordinates
                z=xyz[:,2];u=(xyz[:,0]/z/axis_scale[0]+1)*.5;v=(xyz[:,1]/z/axis_scale[1]+1)*.5
                coordinates=np.stack([v*(mask_height-1),u*(mask_width-1)])
                weights=map_coordinates(selection,coordinates,order=1,mode='constant',cval=0)
                du=map_coordinates(gradient_u,coordinates,order=1,mode='constant',cval=0)
                dv=map_coordinates(gradient_v,coordinates,order=1,mode='constant',cval=0)
                gradient=np.column_stack([du/(2*axis_scale[0]*z),dv/(2*axis_scale[1]*z),
                    -du*xyz[:,0]/(2*axis_scale[0]*z*z)-dv*xyz[:,1]/(2*axis_scale[1]*z*z)])
                xyz,scales,q=semantic_warp(xyz,scales,q,weights,gradient,focus,semantic)
            colors=np.clip(original_colors[start:stop],0,1)
            srgb=np.where(colors<=.0031308,colors*12.92,1.055*colors**(1/2.4)-.055)
            opacity=np.clip(opacities[start:stop],1e-6,1-1e-6)
            attributes[start:stop]=np.column_stack([xyz,(srgb-.5)/.28209479177387814,
                np.log(opacity/(1-opacity)),np.log(scales),q])
        depth_percentiles=(original_depth_percentiles/((1-depth_scale)/focus*original_depth_percentiles+depth_scale)).tolist()
        if depth_exponent!=1:
            depth_percentiles=(focus*np.exp(np.clip(depth_exponent*np.log(original_depth_percentiles/focus),-np.log(20.),np.log(20.)))).tolist()
        if semantic:
            depth_percentiles=np.quantile(attributes[visible,2],[.01,.5,.99]).tolist()
            focus=float(np.median(attributes[visible,2]))
    output=folder/'scene.ply'
    properties=['x','y','z','f_dc_0','f_dc_1','f_dc_2','opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3']
    header='ply\nformat binary_little_endian 1.0\ncomment apple SHARP metric OpenCV coordinates; sRGB SH0\n'
    header+=f'element vertex {count}\n'+''.join(f'property float {name}\n' for name in properties)+'end_header\n'
    temporary=folder/'scene.ply.tmp'
    with temporary.open('wb') as stream:stream.write(header.encode('ascii'));attributes.tofile(stream)
    temporary.replace(output)
    report={**prediction,'scene_url':f'/__sharp-3d/{code}/scene.ply','scene_sha256':digest(output),
        'source_prediction_sha256':digest(folder/'gaussians.npz'),'scene_bytes':output.stat().st_size,
        'coordinate_system':'metric OpenCV camera; rotate X by pi in Three.js',
        'focus_distance':focus,'depth_percentiles':depth_percentiles,
        'camera_fov_y_degrees':float(np.degrees(2*np.arctan(height/(2*focal)))),
        'color_encoding':'sRGB SH0; decode to linear before Gaussian blending, then convert display to sRGB',
        'geometry':'All original Gaussian centers, anisotropic covariance, opacity and colors. No layer rasterization, no original-image plane.'}
    report['depth_override']=override
    if semantic:
        report['semantic_depth']=semantic
        report['effective_relative_inverse_depth_span']=focus*(1/depth_percentiles[0]-1/depth_percentiles[2])
    if depth_scale!=1 or depth_exponent!=1:
        report['depth_compression']={**override,'method':'log-depth-ray-preserving' if depth_exponent!=1 else 'inverse-depth-ray-preserving','focus_anchor':original_focus,
            'original_depth_percentiles':original_depth_percentiles.tolist(),
            'relative_inverse_depth_span':focus*(1/depth_percentiles[0]-1/depth_percentiles[2])}
        report['geometry']='All predicted Gaussians retained. Depth is adjusted along camera rays; full covariance transformed by the projective Jacobian.'
    write(folder/'scene.json',report)
    if not quiet:print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--codes',nargs='+',default=['4016']);args=parser.parse_args()
    for code in args.codes:export(code)
