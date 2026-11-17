"""Resumable local Qwen semantic decomposition; optionally publish after all cases pass."""
from __future__ import annotations
import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import time
import traceback
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def apply_layer_order(result,item):
    requested=item.get('layer_order')
    if not requested and 'generated_layer_order' not in result:return result
    by_name={layer['file']:layer for layer in result['layers']}
    original=result.get('generated_layer_order',[layer['file'] for layer in result['layers']])
    ordered=original
    hashes=item.get('layer_order_hashes',{})
    if requested and set(requested)==set(by_name) and all(by_name.get(name,{}).get('sha256')==sha for name,sha in hashes.items()):ordered=requested
    return {**result,'generated_layer_order':original,'layers':[by_name[name] for name in ordered],
            'render_layer_order':ordered}

def review_for_result(result,review):
    if not review:return {'status':'needs_review'}
    if review.get('status')=='accepted':
        current={layer['file']:layer['sha256'] for layer in result['layers']}
        if review.get('layer_hashes')!=current:return {**review,'status':'needs_review','previous_status':'accepted'}
    return review

def card_for_result(code,result,prefix):
    layers=[];count=len(result['layers']);width,height=result['input_size']
    for i,layer in enumerate(result['layers']):
        layers.append(dict(name=f'qwen_semantic_{i}',path=prefix+layer['file'],x=0,y=0,
            width=712*width/height,height=712,rotation=0,pivot=dict(x=.5,y=.5),opacity=1,
            branch='qwen-semantic',is_title=False,native_z=(count-i)*100,projection_factor=1))
    return dict(layout='canvas',mask_size=712,layers=layers)

class Batch:
    def __init__(self,args):
        self.args=args;self.plan=read(args.plan);self.runtime=Path(args.runtime).resolve()
        self.comfy=self.runtime/'ComfyUI';self.python=self.runtime/'venv/Scripts/python.exe'
        self.batch=self.runtime/'batch';self.batch.mkdir(exist_ok=True)
        self.server=None;self.log=None;self.base=f'http://127.0.0.1:{args.port}'
        self.completed={};self.failures={};self.started=time.time();self.phase='starting';self.current=None

    def fingerprint(self,item):
        value={key:self.plan[key] for key in ['model','quantization','seed','steps','cfg','maximum_dimension']}
        value['seed']=item.get('seed',self.plan['seed'])
        value.update({key:item[key] for key in ['code','layers','caption']})
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def status(self,state='running',**extra):
        value={'state':state,'phase':self.phase,'current':self.current,'completed':len(self.completed),
            'total':len(self.plan['items']),'failed':self.failures,'started_at':self.started,'updated_at':time.time(),**extra}
        write(self.batch/'status.json',value)
        print(json.dumps(value,ensure_ascii=True),flush=True)

    def api(self,path,body=None):
        data=json.dumps(body).encode() if body is not None else None
        request=urllib.request.Request(self.base+path,data=data,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)

    def stop_server(self):
        if self.server and self.server.poll() is None:
            if os.name=='nt':
                subprocess.run(['taskkill','/PID',str(self.server.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:self.server.terminate()
            self.server.wait(timeout=30)
        self.server=None
        if self.log:self.log.close();self.log=None

    def start_server(self,phase):
        # The native mapped reader can crash during repeated encoder loads on Windows.
        # Keep the workaround reproducible and confined to the ignored local runtime.
        shutil.copyfile(Path(__file__).with_name('safe_tensor_loader.py'),self.comfy/'nova_safe_tensor_loader.py')
        utils=self.comfy/'comfy/utils.py'
        source=utils.read_text(encoding='utf8')
        marker='        # nova-rhythm: stream safetensors without native mmap\n'
        if marker not in source:
            needle='    if ckpt.lower().endswith(".safetensors") or ckpt.lower().endswith(".sft"):\n'
            if needle not in source:raise RuntimeError('Unsupported ComfyUI safetensors loader; runtime patch not applied')
            source=source.replace(needle,needle+marker+'        if DISABLE_MMAP and (device is None or device.type == "cpu"):\n            from nova_safe_tensor_loader import load_cpu_safetensors\n            return load_cpu_safetensors(ckpt, return_metadata)\n',1)
            utils.write_text(source,encoding='utf8')
        self.stop_server();self.phase=phase;self.status()
        env={**os.environ,'PYTHONUTF8':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
             'TORCH_HOME':str(self.runtime/'torch-cache'),'TORCHINDUCTOR_CACHE_DIR':str(self.runtime/'torchinductor-cache')}
        self.log=(self.batch/(phase+'.log')).open('ab')
        command=[str(self.python),'main.py','--listen','127.0.0.1','--port',str(self.args.port),
            '--disable-auto-launch','--reserve-vram','0.5','--disable-dynamic-vram',
            '--disable-pinned-memory','--disable-cuda-malloc','--disable-async-offload','--offline','--disable-product-tips']
        if phase=='captions':command.append('--disable-mmap')
        self.server=subprocess.Popen(command,cwd=self.comfy,env=env,stdout=self.log,stderr=self.log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        write(self.batch/'server.json',{'pid':self.server.pid,'command':command,'phase':phase})
        for attempt in range(120):
            if self.server.poll() is not None:raise RuntimeError('ComfyUI failed to start; inspect '+phase+'.log')
            try:self.api('/system_stats');return
            except OSError:time.sleep(1)
        raise RuntimeError('ComfyUI startup timed out')

    def run_graph(self,graph):
        identifier=self.api('/prompt',{'prompt':graph,'client_id':'nova-rhythm-semantic-layering'})['prompt_id']
        write(self.batch/'active-prompt.json',{'id':identifier,'code':self.current,'phase':self.phase})
        last=0
        while True:
            if self.server.poll() is not None:raise RuntimeError('ComfyUI exited; inspect '+self.phase+'.log')
            result=self.api('/history/'+identifier).get(identifier)
            if result:
                if result.get('status',{}).get('status_str')=='error':raise RuntimeError(json.dumps(result['status'],ensure_ascii=True))
                return result
            if time.monotonic()-last>60:self.status(prompt_id=identifier);last=time.monotonic()
            time.sleep(5)

    def prepare_source(self,item):
        from PIL import Image
        folder=self.runtime/item['code'];folder.mkdir(exist_ok=True)
        target=folder/'original.png'
        if not target.exists():
            temporary=folder/'original.download'
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(item['source_url'],timeout=90) as response,temporary.open('wb') as output:
                        shutil.copyfileobj(response,output)
                    break
                except OSError:
                    if attempt==3:raise
                    time.sleep(3*(attempt+1))
            with Image.open(temporary) as image:image.verify()
            temporary.replace(target)
        with Image.open(target) as image:image.verify()
        return item['code'],digest(target)

    def valid_result(self,item,source_hash):
        from PIL import Image
        folder=self.runtime/item['code'];path=folder/'result.json'
        if not path.exists():return None
        result=read(path)
        # The approved first trial predates source_hash; verify its saved source fingerprint.
        recorded=result.get('source_sha256')
        if not recorded:
            legacy=self.runtime/'trial-settings.json'
            recorded=read(legacy).get('input_hashes',{}).get(item['code']) if legacy.exists() else None
        if recorded!=source_hash or result.get('model')!='Qwen-Image-Layered':return None
        if result.get('plan_fingerprint') and result['plan_fingerprint']!=self.fingerprint(item):return None
        if result.get('steps')!=self.plan['steps'] or not item.get('minimum_layers',4)<=len(result.get('layers',[]))<=10:return None
        for layer in result['layers']:
            file=folder/layer['file']
            if not file.exists() or layer.get('sha256')!=digest(file):return None
            with Image.open(file) as image:
                if image.mode!='RGBA':return None
        if not result.get('plan_fingerprint'):
            result['plan_fingerprint']=self.fingerprint(item)
            result['source_sha256']=source_hash
            write(path,result)
        return apply_layer_order(result,item)

    def encode_captions(self,items):
        embeddings=self.comfy/'models/embeddings';embeddings.mkdir(exist_ok=True)
        fingerprints=read(self.batch/'caption-fingerprints.json') if (self.batch/'caption-fingerprints.json').exists() else {}
        texts={'negative':''}|{item['code']:item['caption'] for item in items}
        missing={code:text for code,text in texts.items() if fingerprints.get(code)!=hashlib.sha256(text.encode()).hexdigest() or not (embeddings/(code+'.safetensors')).exists()}
        if not missing:return
        self.start_server('captions')
        graph={'1':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen_2.5_vl_7b_fp8_scaled.safetensors','type':'qwen_image','device':'default'}}}
        for i,(code,text) in enumerate(missing.items()):
            encode=str(i*2+2);save=str(i*2+3)
            graph[encode]={'class_type':'CLIPTextEncode','inputs':{'clip':['1',0],'text':text}}
            graph[save]={'class_type':'SaveConditioning','inputs':{'conditioning':[encode,0],'filename_prefix':'batch-captions/'+code}}
        self.current='all captions';self.run_graph(graph)
        for code,text in missing.items():
            source=sorted((self.comfy/'output/batch-captions').glob(code+'_*.safetensors'))[-1]
            shutil.copyfile(source,embeddings/(code+'.safetensors'))
            fingerprints[code]=hashlib.sha256(text.encode()).hexdigest()
        write(self.batch/'caption-fingerprints.json',fingerprints)
        self.stop_server();self.current=None

    def graph(self,item,layers,seed,size):
        code=item['code']
        def node(kind,**inputs):return {'class_type':kind,'inputs':inputs}
        return {
            '1':node('UnetLoaderGGUF',unet_name='qwen-image-layered-Q4_K_M.gguf'),
            '3':node('VAELoader',vae_name='qwen_image_layered_vae.safetensors'),
            '4':node('LoadImage',image=f'batch-{code}.png'),
            '5':node('VAEEncode',pixels=['4',0],vae=['3',0]),
            '6':node('ConditioningLoader',conditioning_name=code+'.safetensors'),
            '7':node('ConditioningLoader',conditioning_name='negative.safetensors'),
            '8':node('ReferenceLatent',conditioning=['6',0],latent=['5',0]),
            '9':node('ReferenceLatent',conditioning=['7',0],latent=['5',0]),
            '10':node('ModelSamplingAuraFlow',model=['1',0],shift=1.0),
            '11':node('EmptyQwenImageLayeredLatentImage',width=size[0],height=size[1],layers=layers,batch_size=1),
            '12':node('KSampler',model=['10',0],positive=['8',0],negative=['9',0],latent_image=['11',0],
                seed=seed,steps=self.plan['steps'],cfg=self.plan['cfg'],sampler_name='euler',scheduler='simple',denoise=1.0),
            '13':node('LatentCut',samples=['12',0],dim='t',index=1,amount=16384),
            '14':node('LatentCutToBatch',samples=['13',0],dim='t',slice_size=1),
            '15':node('VAEDecode',samples=['14',0],vae=['3',0]),
            '16':node('SaveImage',images=['15',0],filename_prefix=f'batch-{code}/seed-{seed}'),
        }

    def inspect(self,item,outputs,source_hash,size,elapsed,layers,seed):
        import numpy as np
        from PIL import Image
        code=item['code'];folder=self.runtime/code
        images=[];entries=[]
        for i,output in enumerate(outputs):
            source=self.comfy/'output'/output['subfolder']/output['filename']
            target=folder/f'layer-{i:02d}.png';shutil.copyfile(source,target)
            image=Image.open(target).convert('RGBA');alpha=np.asarray(image)[:,:,3]
            if int((alpha>8).sum())<16:continue
            images.append(image)
            entries.append({'file':target.name,'size':list(image.size),'mode':'RGBA','sha256':digest(target),'visible_fraction':round(float((alpha>8).mean()),6)})
        minimum=item.get('minimum_layers',4)
        if not minimum<=len(entries)<=10:raise RuntimeError(f'Output does not contain {minimum}–10 nonempty RGBA layers')
        source=Image.open(folder/'input.png').convert('RGB')
        def composite(sequence):
            result=Image.new('RGBA',size)
            for image in sequence:result.alpha_composite(image)
            return result
        def error(image):return float(np.abs(np.asarray(image.convert('RGB'),dtype=float)-np.asarray(source,dtype=float)).mean())
        merged=composite(images);reverse=composite(images[::-1])
        if error(reverse)<error(merged):entries.reverse();merged=reverse
        merged.save(folder/'reconstructed.png')
        result={**item,'model':'Qwen-Image-Layered','quantization':self.plan['quantization'],'source_sha256':source_hash,'plan_fingerprint':self.fingerprint(item),
            'seed':seed,'steps':self.plan['steps'],'cfg':self.plan['cfg'],'requested_layers':layers,'input_size':size,
            'layers':entries,'layer_order':'back-to-front','elapsed_seconds':round(elapsed,1),'composite_mae_255':round(error(merged),3)}
        result=apply_layer_order(result,item)
        write(folder/'result.json',result)
        return result

    def update_local(self):
        overrides={code:card_for_result(code,result,f'/__layering-trial/{code}/') for code,result in self.completed.items()}
        write(self.runtime/'local-overrides.json',overrides)
        write(self.batch/'results.json',self.completed)
        path=ROOT/'references/experimental-layering-reviews.json'
        reviews=read(path).get('items',{}) if path.exists() else {}
        write(self.batch/'reviews.json',{code:review_for_result(result,reviews.get(code)) for code,result in self.completed.items()})

    def run(self):
        from PIL import Image
        if os.name=='nt':ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            self.phase='sources';self.status()
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                hashes=dict(pool.map(self.prepare_source,self.plan['items']))
            for item in self.plan['items']:
                result=self.valid_result(item,hashes[item['code']])
                if result:self.completed[item['code']]=result
            failed_fingerprints={};case_index=0
            while True:
                # Pick up review-driven edits only at image checkpoints, preserving current work.
                for attempt in range(30):
                    try:self.plan=read(self.args.plan);break
                    except (OSError,ValueError):
                        if attempt==29:raise
                        time.sleep(1)
                if self.plan.get('generation',{}).get('enabled') is False:
                    self.phase='awaiting-hd-validation';self.status('awaiting-hd-validation');return
                active_codes={item['code'] for item in self.plan['items']}
                self.completed={code:result for code,result in self.completed.items() if code in active_codes}
                remaining=[]
                for item in self.plan['items']:
                    code=item['code'];fingerprint=self.fingerprint(item)
                    if code not in hashes:_,hashes[code]=self.prepare_source(item)
                    if code in self.completed and self.completed[code].get('plan_fingerprint')!=fingerprint:self.completed.pop(code)
                    if code in self.completed:
                        self.completed[code]=apply_layer_order(self.completed[code],item)
                        continue
                    if code in self.failures and failed_fingerprints.get(code)==fingerprint:continue
                    self.failures.pop(code,None)
                    cached=self.valid_result(item,hashes[code])
                    if cached:self.completed[code]=cached
                    else:remaining.append(item)
                self.update_local()
                if not remaining:break
                remaining.sort(key=lambda item:-int(item.get('priority',0)))
                for caption_attempt in range(3):
                    try:
                        self.encode_captions(remaining);break
                    except Exception:
                        write(self.batch/f'caption-error-{caption_attempt}.json',{'traceback':traceback.format_exc()})
                        self.stop_server()
                        if caption_attempt==2:raise
                if self.server is None or self.server.poll() is not None:self.start_server('sampling')
                item=remaining[0];code=item['code'];self.current={'code':code,'name':item['name']};self.status()
                folder=self.runtime/code
                image=Image.open(folder/'original.png').convert('RGB');width,height=image.size
                scale=self.plan['maximum_dimension']/max(width,height)
                size=[round(width*scale/16)*16,round(height*scale/16)*16]
                image=image.resize(size,Image.Resampling.LANCZOS);image.save(folder/'input.png');image.save(self.comfy/'input'/f'batch-{code}.png')
                for attempt in range(3):
                    layers=min(10,item['layers']+(1 if attempt==2 else 0));seed=item.get('seed',self.plan['seed'])+(1 if attempt==1 else 0)
                    try:
                        if self.server is None or self.server.poll() is not None:self.start_server('sampling')
                        graph=self.graph(item,layers,seed,size);write(folder/'workflow-api.json',graph)
                        started=time.monotonic();history=self.run_graph(graph)
                        outputs=history.get('outputs',{}).get('16',{}).get('images',[])
                        result=self.inspect(item,outputs,hashes[code],size,time.monotonic()-started,layers,seed)
                        self.completed[code]=result;self.update_local();self.status();break
                    except Exception:
                        write(folder/f'error-attempt-{attempt}.json',{'traceback':traceback.format_exc()})
                        self.stop_server()
                        if attempt==2:
                            self.failures[code]='Failed after three attempts; see per-case error files'
                            failed_fingerprints[code]=self.fingerprint(item)
                case_index+=1
                if case_index%4==0:self.stop_server()
            self.stop_server();self.current=None
            if self.failures:raise RuntimeError('Some cases failed; publication withheld until all cases pass')
            self.phase='inference-complete';self.status()
            if self.args.publish:
                from publish_layers import publish
                self.phase='publishing';self.status()
                if publish(self) is False:
                    self.phase='awaiting-review';self.status('awaiting-review');return
            self.phase='complete';self.status('complete')
        except Exception:
            self.status('failed',error=traceback.format_exc());raise
        finally:
            self.stop_server()
            if os.name=='nt':ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime',default=str(ROOT/'.build/layering-trial'))
    parser.add_argument('--plan',default=str(ROOT/'references/experimental-layering-plan.json'))
    parser.add_argument('--port',type=int,default=8189)
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args();Batch(args).run()

if __name__=='__main__':main()
