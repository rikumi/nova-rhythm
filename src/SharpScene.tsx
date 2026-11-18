import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { SparkRenderer, SplatMesh } from '@sparkjsdev/spark';
import { deviceTilt } from './deviceTilt';
import { loadSharpScene, sharpSourceUrl, sharpRenderInfo } from './sharpScenes';
import { loadSceneData } from './sharpSceneData';
import { bindModelSource } from './sharpModelCache';
import { useArtworkPointer } from './useArtworkPointer';
import './sharpScene.css';

export default function SharpScene({full=false,suspended=false,code='4016',name='春日纪事'}:{full?:boolean;suspended?:boolean;code?:string;name?:string}){
  const host=useRef<HTMLDivElement>(null);
  const canvasHost=useRef<HTMLDivElement>(null);
  const lightRef=useRef<HTMLDivElement>(null);
  const artworkPointer=useArtworkPointer(host,lightRef);
  const pointer=useRef({x:0,y:0,active:false,id:-1});
  const paused=useRef(suspended);paused.current=suspended;
  const [status,setStatus]=useState('正在加载三维场景…');
  const [error,setError]=useState('');
  useEffect(()=>{
    const element=host.current;if(!element||suspended)return;
    setStatus('正在加载三维场景…');setError('');
    let disposed=false,frame=0,dirty=true,wasPaused=false;
    let renderer:THREE.WebGLRenderer|undefined,spark:SparkRenderer|undefined,mesh:SplatMesh|undefined;
    let target:THREE.WebGLRenderTarget|undefined,plane:THREE.Mesh<THREE.PlaneGeometry,THREE.MeshBasicMaterial>|undefined;
    let observer:ResizeObserver|undefined;
    const abort=new AbortController();
    const contextLost=(event:Event)=>{event.preventDefault();if(!disposed){delete element.dataset.ready;setError('三维画面暂时无法显示');}};
    void (async()=>{
      try{
        const info=sharpRenderInfo(await loadSharpScene(code,import.meta.env.DEV,abort.signal));if(disposed)return;
        const compressed=info.scene_format==='ply+gzip';
        const source=sharpSourceUrl(info);
        const bytes=await loadSceneData(source,compressed?info.compressed_bytes:info.scene_bytes,abort.signal,state=>{
            if(disposed)return;
            if(state.phase==='download')setStatus(state.total?`正在下载三维场景 ${Math.floor((state.loaded||0)/state.total*100)}%`:'正在下载三维场景…');
            else if(state.phase==='retry')setStatus(`正在重试下载 ${state.attempt}/3…`);
            else if(state.phase==='decompress')setStatus('正在解压三维场景…');
            else setStatus('正在解析三维场景…');
          },compressed);
          if(disposed)return;
        bindModelSource(code,source);
        element.dataset.source='precomputed';
        element.dataset.renderer='webgl2-gaussian-splats';
        const scene=new THREE.Scene();scene.background=new THREE.Color(.012,.018,.028);
        const camera=new THREE.PerspectiveCamera(info.camera_fov_y_degrees,info.input_size[0]/info.input_size[1],.001,Math.max(100,info.focus_distance*100));
        renderer=new THREE.WebGLRenderer({antialias:false,alpha:false,powerPreference:'high-performance'});
        renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
        renderer.domElement.setAttribute('aria-label',`${name} SHARP 三维场景`);
        renderer.domElement.addEventListener('webglcontextlost',contextLost);
        canvasHost.current?.append(renderer.domElement);
        // PLY carries sRGB SH0. Spark decodes it into this linear render target;
        // the final Three.js pass performs one linear-to-sRGB display conversion.
        target=new THREE.WebGLRenderTarget(1,1,{type:renderer.extensions.has('EXT_color_buffer_float')?THREE.HalfFloatType:THREE.UnsignedByteType,depthBuffer:false});
        target.texture.colorSpace=THREE.LinearSRGBColorSpace;
        const postScene=new THREE.Scene(),postCamera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
        plane=new THREE.Mesh(new THREE.PlaneGeometry(2,2),new THREE.MeshBasicMaterial({map:target.texture,depthTest:false,depthWrite:false,toneMapped:false}));
        plane.frustumCulled=false;postScene.add(plane);
        const {SparkRenderer,SplatMesh}=await import('@sparkjsdev/spark');if(disposed)return;
        spark=new SparkRenderer({renderer,accumExtSplats:true,sortRadial:false,blurAmount:0,preBlurAmount:0,maxStdDev:3,onDirty:()=>{dirty=true;}});
        scene.add(spark);
        mesh=new SplatMesh({url:bytes?undefined:info.scene_url,fileBytes:bytes,fileName:`${code}.ply`,extSplats:true,lod:false,enableLod:false,raycastable:false,
          onProgress:event=>{if(!disposed)setStatus(event.lengthComputable?`正在解析三维场景 ${Math.round(event.loaded/event.total*100)}%…`:'正在解析三维场景…');}});
        mesh.rotation.x=Math.PI;
        scene.add(mesh);
        let x=0,y=0,previous=performance.now(),renders=0,initialized=false,painted=false;
        // Keep the rotation pivot in front of the useful scene depth range, so
        // foreground and background both shift opposite to the pointer.
        const pivotDistance=(info.depth_percentiles?.[0]||info.focus_distance*.65)*.7;
        element.dataset.pivotDistance=String(pivotDistance);
        const frameStyle=element.closest<HTMLElement>('.live-card')?.style;
        let previousMx='',previousMy='';
        const resize=()=>{
          if(!renderer||!target)return;
          const width=element.clientWidth,height=element.clientHeight;if(!width||!height)return;
          renderer.setSize(width,height,false);
          const pixels=new THREE.Vector2();renderer.getDrawingBufferSize(pixels);target.setSize(pixels.x,pixels.y);
          const [iw,ih]=info.input_size,ratio=width/height;
          const viewWidth=full?Math.max(iw,ih*ratio):Math.min(iw,ih*ratio);
          const viewHeight=viewWidth/ratio;
          camera.setViewOffset(iw,ih,(iw-viewWidth)/2,(ih-viewHeight)/2,viewWidth,viewHeight);
          camera.updateProjectionMatrix();dirty=true;
        };
        observer=new ResizeObserver(resize);observer.observe(element);resize();
        const tick=(now:number)=>{
          if(disposed)return;
          frame=requestAnimationFrame(tick);
          if(paused.current){wasPaused=true;previous=now;return;}
          if(wasPaused){dirty=true;wasPaused=false;}
          const sensor=deviceTilt.read(now),input=pointer.current.active?pointer.current:sensor.active?sensor:{x:0,y:0};
          const k=1-Math.exp(-Math.min(now-previous,100)/220);previous=now;
          x+=(input.x-x)*k;y+=(input.y-y)*k;
          if(Math.abs(x)<.0001&&input.x===0)x=0;if(Math.abs(y)<.0001&&input.y===0)y=0;
          const mx=String(Math.round(x*1000)/1000),my=String(Math.round(y*1000)/1000);
          if(frameStyle&&mx!==previousMx){frameStyle.setProperty('--mx',mx);previousMx=mx;}
          if(frameStyle&&my!==previousMy){frameStyle.setProperty('--my',my);previousMy=my;}
          const cx=Math.round(-x*pivotDistance*.065*1e4)/1e4,cy=Math.round(y*pivotDistance*.045*1e4)/1e4;
          if(camera.position.x!==cx||camera.position.y!==cy){
            camera.position.set(cx,cy,0);camera.lookAt(0,0,-pivotDistance);dirty=true;
            element.dataset.cameraX=String(cx);element.dataset.cameraY=String(cy);
          }
          if(dirty&&renderer&&target){
            dirty=false;renderer.setRenderTarget(target);renderer.render(scene,camera);
            renderer.setRenderTarget(null);renderer.render(postScene,postCamera);
            element.dataset.renderCount=String(++renders);
            if(initialized&&!painted){painted=true;element.dataset.ready='true';setStatus('');}
          }
        };
        frame=requestAnimationFrame(tick);
        await mesh?.initialized;
        if(disposed){mesh?.dispose();return;}
        if(mesh)element.dataset.splatCount=String(info.gaussian_count);initialized=true;dirty=true;
      }catch(reason){if(!disposed&&!abort.signal.aborted){delete element.dataset.ready;setError(reason instanceof Error?reason.message:'三维场景加载失败');}}
    })();
    return()=>{
      disposed=true;abort.abort();cancelAnimationFrame(frame);observer?.disconnect();
      delete element.dataset.ready;
      mesh?.dispose();spark?.dispose();plane?.geometry.dispose();plane?.material.dispose();target?.dispose();
      if(renderer){renderer.domElement.removeEventListener('webglcontextlost',contextLost);renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();}
    };
  },[full,code,name,suspended]);
  const move=(event:React.PointerEvent<HTMLDivElement>)=>{
    if(event.pointerType!=='mouse'&&pointer.current.id!==event.pointerId)return;
    pointer.current={...pointer.current,...artworkPointer.sample(event)};
  };
  const hideLight=artworkPointer.hide;
  const release=(event:React.PointerEvent<HTMLDivElement>)=>{
    pointer.current={x:0,y:0,active:false,id:-1};
    if(event.pointerType!=='mouse')hideLight();
    if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
  };
  return <div ref={host} className="sharp-scene" data-renderer="webgl2-gaussian-splats" onPointerMove={move}
    onPointerDown={event=>{if(event.target instanceof Element&&event.target.closest('button'))return;artworkPointer.reset();if(event.pointerType!=='mouse'){event.preventDefault();pointer.current.id=event.pointerId;event.currentTarget.setPointerCapture(event.pointerId);move(event);}}}
    onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}
    onPointerLeave={()=>{if(pointer.current.id===-1)pointer.current={x:0,y:0,active:false,id:-1};hideLight();}}>
    <div ref={canvasHost} className="sharp-canvas" />
    <div ref={lightRef} className="card-light" aria-hidden="true" />
    {(status||error)&&<div className="card-loading-toast" role="status">{error||status}</div>}
  </div>;
}
