"""Upload only static 3D assets to a separate Release; never commit, push or deploy."""
import datetime
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/layering'))
from run_batch import digest,read,write


def validate_scene(path,report):
    import numpy as np
    with path.open('rb') as stream:
        header=b''
        while not header.endswith(b'end_header\n'):
            line=stream.readline()
            if not line or len(header)>65536:raise RuntimeError('Invalid PLY header: '+str(path))
            header+=line
    lines=header.decode('ascii').splitlines()
    if 'format binary_little_endian 1.0' not in lines:raise RuntimeError('Unexpected PLY encoding')
    count=int(next(line.split()[-1] for line in lines if line.startswith('element vertex ')))
    if count!=report['gaussian_count'] or path.stat().st_size!=len(header)+count*14*4:raise RuntimeError('PLY size/count mismatch')
    data=np.memmap(path,dtype='<f4',mode='r',offset=len(header),shape=(count,14))
    if not np.isfinite(data).all():raise RuntimeError('Non-finite scene attributes')
    if not np.allclose(np.linalg.norm(data[:,10:14],axis=1),1,atol=2e-6):raise RuntimeError('Invalid scene quaternion')
    if digest(path)!=report['scene_sha256']:raise RuntimeError('Scene SHA256 mismatch')


def publish(runtime,plan,results):
    if set(results)!=set(item['code'] for item in plan['items']):raise RuntimeError('All static outfits must finish before publication')
    gh=str(ROOT/'tools/github-cli/portable/bin/gh.exe')
    repository='rikumi/nova-rhythm'
    date=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d')
    tag='sharp-scenes-'+date
    output=runtime/'batch/release-assets';output.mkdir(parents=True,exist_ok=True)
    base=f'https://github.com/{repository}/releases/download/{tag}'
    manifest={'schemaVersion':1,'model':'apple/Sharp','format':'PLY + lossless gzip','coordinate_system':'metric OpenCV; rotate X by pi for Three.js',
        'release_url':f'https://github.com/{repository}/releases/tag/{tag}','settings':plan['settings'],'outfits':{}}
    assets=[]
    def add(path):assets.append({'path':str(path),'name':path.name,'size':path.stat().st_size,'sha256':digest(path)})
    for item in plan['items']:
        code=item['code'];report=results[code];source=runtime/code/'scene.ply'
        validate_scene(source,report)
        target=output/f'{code}-{report["scene_sha256"][:12]}.ply.gz'
        cache=target.with_suffix('.cache.json')
        cached=read(cache) if cache.exists() else {}
        if not target.exists() or cached.get('sha256')!=digest(target):
            temporary=target.with_suffix('.tmp')
            with source.open('rb') as src,temporary.open('wb') as dst:
                with gzip.GzipFile(filename='',mode='wb',compresslevel=3,fileobj=dst,mtime=0) as compressed:shutil.copyfileobj(src,compressed,1024*1024)
            temporary.replace(target);write(cache,{'sha256':digest(target)})
        # Verify decompression against the authoritative float32 PLY, not just the gzip file.
        with gzip.open(target,'rb') as stream:
            import hashlib
            if hashlib.file_digest(stream,'sha256').hexdigest()!=report['scene_sha256']:raise RuntimeError('Lossless scene verification failed')
        metadata={**report,'scene_url':base+'/'+target.name,'scene_format':'ply+gzip','compressed_bytes':target.stat().st_size,
            'compressed_sha256':digest(target),'original_image_url':item['source_url']}
        metadata_file=output/(code+'.json');write(metadata_file,metadata)
        manifest['outfits'][code]={**metadata,'metadata_url':base+'/'+metadata_file.name}
        add(target);add(metadata_file)
        print('Prepared',code,len(manifest['outfits']),'/',len(plan['items']),'compressed MiB',round(target.stat().st_size/1024**2,1),flush=True)
    manifest_file=output/'sharp-scenes.json';write(manifest_file,manifest);add(manifest_file)
    inputs=output/'processing-plan.json';write(inputs,plan);add(inputs)
    license_file=output/'APPLE_SHARP_LICENSE_MODEL.txt';shutil.copyfile(runtime/'ml-sharp/LICENSE_MODEL',license_file);add(license_file)
    notes=runtime/'batch/release-notes.txt'
    notes.write_text(f'{len(results)} static outfits generated locally with Apple SHARP.\n\n'
        'Each scene preserves all predicted Gaussian centers, full oriented covariance, colors and opacity in a float32 PLY. '
        'Gzip compression is lossless and every decompressed scene is verified against its original PLY SHA256. '
        'No image layers or model weights are uploaded.\n\n'
        'The sharp-scenes.json manifest includes source hashes, camera intrinsics, scene hashes and download URLs. '
        'This release does not deploy or change the website.\n\n'
        'Apple Machine Learning Research Model is licensed under the Apple Machine Learning Research Model License Agreement.\n'
        'Model: https://github.com/apple/ml-sharp\n'
        'Original game artwork remains copyright of its respective owners.\n',encoding='utf8')
    def cli(*args,check=True):
        result=subprocess.run([gh,*map(str,args)],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
        if check and result.returncode:raise RuntimeError(result.stderr)
        return result
    existing=cli('release','view',tag,'--repo',repository,'--json','id',check=False)
    if existing.returncode:
        cli('release','create',tag,'--repo',repository,'--target','main','--draft',
            '--title','SHARP 3D outfit scenes '+date,'--notes-file',notes)
    pages=json.loads(cli('api',f'repos/{repository}/releases?per_page=100','--paginate','--slurp').stdout)
    release=next(release for page in pages for release in page if release['tag_name']==tag)
    def remote_assets():
        pages=json.loads(cli('api',f'repos/{repository}/releases/{release["id"]}/assets?per_page=100','--paginate','--slurp').stdout)
        return {asset['name']:asset for page in pages for asset in page}
    remote=remote_assets()
    # Remove only superseded versions of scenes explicitly corrected by
    # the user; preserve all unrelated release assets and the original local PLYs.
    import re
    expected_names={asset['name'] for asset in assets}
    corrected_codes=set(plan.get('depth_overrides',{}).get('outfits',{}))
    corrected_codes.update(plan.get('semantic_overrides',{}).get('outfits',{}))
    for name in remote:
        if re.fullmatch(r'\d{4}-[0-9a-f]{12}\.ply\.gz',name) and name[:4] in corrected_codes and name not in expected_names:
            cli('api','--method','DELETE',f'repos/{repository}/releases/assets/{remote[name]["id"]}')
    pending=[asset for asset in assets if remote.get(asset['name'],{}).get('digest')!='sha256:'+asset['sha256']
             or remote.get(asset['name'],{}).get('size')!=asset['size']]
    for start in range(0,len(pending),6):
        group=pending[start:start+6]
        for attempt in range(4):
            response=cli('release','upload',tag,*[asset['path'] for asset in group],'--repo',repository,'--clobber',check=False)
            if not response.returncode:break
            if attempt==3:raise RuntimeError(response.stderr)
            time.sleep(5*(attempt+1))
        print('Uploaded',min(start+6,len(pending)),'/',len(pending),'assets',flush=True)
    remote=remote_assets()
    for asset in assets:
        stored=remote.get(asset['name'],{})
        if stored.get('digest')!='sha256:'+asset['sha256'] or stored.get('size')!=asset['size']:
            raise RuntimeError('Remote verification failed: '+asset['name'])
    cli('release','edit',tag,'--repo',repository,'--draft=false','--latest=false','--notes-file',notes)
    publication={'release_url':manifest['release_url'],'manifest_url':base+'/sharp-scenes.json','outfits':len(results),
        'assets':len(assets),'total_bytes':sum(asset['size'] for asset in assets),'verified':True,'website_deployed':False}
    write(runtime/'batch/publication.json',publication)
    write(ROOT/'references/sharp-scenes-results.json',{'schemaVersion':1,'publication':publication,'outfits':manifest['outfits']})
    print(json.dumps(publication),flush=True)


if __name__=='__main__':
    runtime=ROOT/'.build/sharp-layering'
    publish(runtime,read(ROOT/'references/sharp-scenes-plan.json'),read(runtime/'batch/results.json'))
