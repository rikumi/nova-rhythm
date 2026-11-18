import test from 'node:test';
import assert from 'node:assert/strict';
import {readLayerPackage} from '../../src/sharpDepthLayers.ts';
import {sharpRenderInfo,sharpSourceUrl,sharpDownloadBytes} from '../../src/sharpScenes.ts';

function fixture(change=()=>{}){
  const header={format:'sharp-depth-layers-v1',input_size:[2400,1700],camera_fov_y_degrees:45,
    layers:Array.from({length:20},(_,i)=>({depth:1+i/10,offset:i,length:1,rect:[10,20,100,200]}))};
  change(header);const encoded=new TextEncoder().encode(JSON.stringify(header)),bytes=new Uint8Array(8+encoded.length+20);
  bytes.set([83,68,76,49]);new DataView(bytes.buffer).setUint32(4,encoded.length,true);bytes.set(encoded,8);return bytes.buffer;
}
test('depth packages preserve all twenty planes and the original crop coordinates',()=>{
  const {header,start}=readLayerPackage(fixture());assert.equal(header.layers.length,20);
  assert.deepEqual(header.layers[4].rect,[10,20,100,200]);assert.equal(header.layers[19].depth,2.9);assert.ok(start>8);
});
test('truncated, overlapping, unordered and oversized layer packages are rejected',()=>{
  assert.throws(()=>readLayerPackage(fixture().slice(0,-1)));
  assert.throws(()=>readLayerPackage(fixture(h=>h.layers[1].offset=0)));
  assert.throws(()=>readLayerPackage(fixture(h=>h.layers[2].depth=.5)));
  assert.throws(()=>readLayerPackage(fixture(h=>h.layers[0].rect=[0,0,3000,1])));
  assert.throws(()=>readLayerPackage(fixture(h=>h.input_size=[999999,1])));
  assert.throws(()=>readLayerPackage(new ArrayBuffer(3)));
});
test('touch devices use the image package consistently for loading, cache keys and size',()=>{
  const original=globalThis.matchMedia;
  const info={scene_url:'https://test/model.ply.gz',scene_format:'ply+gzip',compressed_bytes:59000000,scene_sha256:'original',layer_scene:{url:'https://test/model.layers',bytes:17000000,sha256:'layers',layer_count:20}};
  try{
    globalThis.matchMedia=()=>({matches:true});
    assert.equal(sharpRenderInfo(info).scene_format,'depth-layers');assert.equal(sharpDownloadBytes(info),17000000);
    assert.equal(sharpSourceUrl(info),'https://test/model.layers?v=layers');assert.equal(sharpSourceUrl(sharpRenderInfo(info)),sharpSourceUrl(info));
    globalThis.matchMedia=()=>({matches:false});assert.equal(sharpSourceUrl(info),info.scene_url);assert.equal(sharpDownloadBytes(info),59000000);
  }finally{globalThis.matchMedia=original;}
});
