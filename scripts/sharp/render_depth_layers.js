// Offline-only Vite module. Never imported by the application.
import * as THREE from 'three';
import {SparkRenderer, SplatMesh, dyno} from '@sparkjsdev/spark';

window.bakeDepthLayers = async function(item) {
  const [width,height]=item.input_size;
  const renderer=new THREE.WebGLRenderer({antialias:false,alpha:true,premultipliedAlpha:false});
  renderer.setSize(width,height);renderer.setPixelRatio(1);renderer.setClearColor(0,0);
  renderer.outputColorSpace=THREE.LinearSRGBColorSpace;
  if(!renderer.extensions.has('EXT_color_buffer_float'))throw Error('Float color rendering is required');
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(item.camera_fov_y_degrees,width/height,.001,1000);
  const target=new THREE.WebGLRenderTarget(width,height,{type:THREE.HalfFloatType,depthBuffer:false});
  target.texture.colorSpace=THREE.LinearSRGBColorSpace;
  const output=new THREE.WebGLRenderTarget(width,height,{depthBuffer:false});
  const postScene=new THREE.Scene(),postCamera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
  const material=new THREE.ShaderMaterial({uniforms:{image:{value:target.texture}},depthTest:false,depthWrite:false,blending:THREE.NoBlending,
    vertexShader:'varying vec2 uvOut;void main(){uvOut=uv;gl_Position=vec4(position.xy,0.,1.);}',
    fragmentShader:`uniform sampler2D image;varying vec2 uvOut;
      void main(){vec4 c=texture2D(image,uvOut);vec3 v=c.a>0.00001?c.rgb/c.a:vec3(0.);
      vec3 s=mix(v*12.92,1.055*pow(max(v,vec3(0.)),vec3(1./2.4))-.055,step(vec3(.0031308),v));gl_FragColor=vec4(s,c.a);}`});
  const plane=new THREE.Mesh(new THREE.PlaneGeometry(2,2),material);postScene.add(plane);
  const spark=new SparkRenderer({renderer,accumExtSplats:true,sortRadial:false,blurAmount:0,preBlurAmount:0,maxStdDev:3});scene.add(spark);
  const mesh=new SplatMesh({url:`/__depth-bake/model/${item.code}.ply`,extSplats:true,lod:false,enableLod:false,raycastable:false});
  mesh.rotation.x=Math.PI;scene.add(mesh);
  const pixels=new Uint8Array(width*height*4);
  try {
    await mesh.initialized;
    for(let index=-1;index<20;index++){
      if(index>=0){
        const near=item.depths[0],step=(item.depths[19]-near)/19;
        mesh.objectModifier=new dyno.Dyno({inTypes:{gsplat:dyno.Gsplat},outTypes:{gsplat:dyno.Gsplat},
          statements:({inputs,outputs})=>[`${outputs.gsplat}=${inputs.gsplat};
            float slice=floor(clamp((${inputs.gsplat}.center.z-${near.toFixed(12)})/${Math.max(step,1e-12).toFixed(12)}+0.5,0.0,19.0));
            if(slice!=${index}.0){${outputs.gsplat}.rgba.a=0.0;${outputs.gsplat}.flags=0u;}`]});
        mesh.updateGenerator();spark.setDirty();
      }
      await spark.update({scene,camera});
      renderer.setRenderTarget(target);renderer.clear();renderer.render(scene,camera);
      renderer.setRenderTarget(output);renderer.clear();renderer.render(postScene,postCamera);
      renderer.readRenderTargetPixels(output,0,0,width,height,pixels);
      const response=await fetch(`/__depth-bake/frame/${item.code}/${index<0?'reference':index}.rgba`,{method:'POST',body:pixels});
      if(!response.ok)throw Error('Cannot save rendered layer');
    }
    return {code:item.code};
  } finally {
    mesh.dispose();spark.dispose();plane.geometry.dispose();material.dispose();target.dispose();output.dispose();renderer.dispose();renderer.forceContextLoss();
  }
};
