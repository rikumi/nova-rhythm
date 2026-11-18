import * as THREE from 'three';

interface LayerHeader {format:string;input_size:[number,number];camera_fov_y_degrees:number;layers:{depth:number;offset:number;length:number;rect?:[number,number,number,number]}[];}
export function readLayerPackage(bytes:ArrayBuffer):{header:LayerHeader;start:number}{
  const view=new DataView(bytes);
  if(bytes.byteLength<8||view.getUint32(0,false)!==0x53444c31)throw Error('Invalid depth-layer package');
  const length=view.getUint32(4,true),start=8+length;
  if(start>bytes.byteLength)throw Error('Truncated depth-layer header');
  const header=JSON.parse(new TextDecoder().decode(new Uint8Array(bytes,8,length))) as LayerHeader;
  if(header.format!=='sharp-depth-layers-v1'||header.layers.length!==20)throw Error('Expected 20 depth layers');
  if(!Array.isArray(header.input_size)||header.input_size.length!==2||header.input_size.some(v=>!Number.isInteger(v)||v<=0||v>16384)||!Number.isFinite(header.camera_fov_y_degrees)||header.camera_fov_y_degrees<=0||header.camera_fov_y_degrees>=180)throw Error('Invalid depth-layer camera');
  let end=0,depth=0;
  for(const layer of header.layers){
    if(!Number.isFinite(layer.depth)||layer.depth<depth||layer.depth<=0||layer.offset!==end||!Number.isInteger(layer.length)||layer.length<=0||start+layer.offset+layer.length>bytes.byteLength)throw Error('Invalid depth-layer entry');
    if(layer.rect){const [x,y,w,h]=layer.rect;if(layer.rect.length!==4||layer.rect.some(v=>!Number.isInteger(v))||x<0||y<0||w<=0||h<=0||x+w>header.input_size[0]||y+h>header.input_size[1])throw Error('Invalid depth-layer crop');}
    end+=layer.length;depth=layer.depth;
  }
  if(start+end!==bytes.byteLength)throw Error('Unexpected depth-layer payload');
  return {header,start};
}
export async function createDepthPlanes(bytes:ArrayBuffer,signal:AbortSignal,onProgress:(loaded:number,total:number)=>void){
  const {header,start}=readLayerPackage(bytes),planes:THREE.Mesh<THREE.PlaneGeometry,THREE.MeshBasicMaterial>[]=[],bitmaps:ImageBitmap[]=[];
  const dispose=()=>{for(const plane of planes){plane.geometry.dispose();plane.material.map?.dispose();plane.material.dispose();}for(const bitmap of bitmaps)bitmap.close();};
  try{
    const tangent=Math.tan(header.camera_fov_y_degrees*Math.PI/360),aspect=header.input_size[0]/header.input_size[1];
    // Decode serially to keep peak temporary memory bounded on phones.
    for(const [index,layer] of header.layers.entries()){
      signal.throwIfAborted();
      const blob=new Blob([new Uint8Array(bytes,start+layer.offset,layer.length)],{type:'image/webp'});
      const bitmap=await createImageBitmap(blob,{imageOrientation:'flipY',premultiplyAlpha:'premultiply',colorSpaceConversion:'none'});
      bitmaps.push(bitmap);signal.throwIfAborted();
      const texture=new THREE.Texture(bitmap);texture.colorSpace=THREE.NoColorSpace;texture.generateMipmaps=true;
      texture.minFilter=THREE.LinearMipmapLinearFilter;texture.magFilter=THREE.LinearFilter;texture.needsUpdate=true;
      const height=2*layer.depth*tangent,width=height*aspect,[iw,ih]=header.input_size;
      const [left,top,pw,ph]=layer.rect||[0,0,iw,ih];
      const plane=new THREE.Mesh(new THREE.PlaneGeometry(width*pw/iw,height*ph/ih),new THREE.MeshBasicMaterial({map:texture,transparent:true,depthTest:false,depthWrite:false,toneMapped:false}));
      // Filter associated sRGB samples, then recover straight color and decode to
      // linear for blending. Filtering straight-alpha masks creates black seams.
      plane.material.onBeforeCompile=shader=>{
        shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',
          `vec4 texel=texture2D(map,vMapUv); vec3 straight=texel.rgb/max(texel.a,0.00001);
           diffuseColor*=vec4(sRGBTransferEOTF(vec4(straight,1.0)).rgb,texel.a);`);
      };
      plane.position.set(((left+pw/2)/iw-.5)*width,(.5-(top+ph/2)/ih)*height,-layer.depth);
      plane.renderOrder=-index;plane.frustumCulled=false;planes.push(plane);onProgress(index+1,20);
    }
    return {planes,dispose};
  }catch(error){dispose();throw error;}
}
