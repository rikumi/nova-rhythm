import assert from 'node:assert/strict';
import test from 'node:test';
import {gzipSync} from 'node:zlib';
import {loadSceneData} from '../../src/sharpSceneData.ts';
import {bindModelSource,modelCacheState,setModelCached} from '../../src/sharpModelCache.ts';

const original=Buffer.from('ply\nformat binary_little_endian 1.0\nend_header\n');
const gzip=gzipSync(original);
const signal=()=>new AbortController().signal;

test('shared normal/fullscreen loads survive one subscriber cancelling and reuse decoded data',async()=>{
  const previous=globalThis.fetch;let calls=0,release;
  const gate=new Promise(resolve=>release=resolve),first=new AbortController(),progress=()=>{};
  globalThis.fetch=async()=>{calls++;await gate;return new Response(gzip);};
  try{
    const a=loadSceneData('/shared',gzip.length,first.signal,progress);
    const b=loadSceneData('/shared',gzip.length,signal(),progress);
    first.abort();await assert.rejects(a,{name:'AbortError'});release();
    const bytes=await b;
    assert.deepEqual(Buffer.from(bytes),original);assert.equal(calls,1);
    assert.equal(await loadSceneData('/shared',gzip.length,signal(),progress),bytes);assert.equal(calls,1);
  }finally{globalThis.fetch=previous;}
});

test('persistent storage is opt-in, deleting it preserves memory, and recaching needs no download',async()=>{
  const fetcher=globalThis.fetch,storage=globalThis.caches,entries=new Map();let calls=0;
  const cache={match:async key=>entries.get(key)?.clone(),put:async(key,response)=>{entries.set(key,response.clone());},
    keys:async()=>[...entries.keys()],delete:async key=>entries.delete(key)};
  globalThis.caches={open:async()=>cache};
  globalThis.fetch=async()=>{calls++;return new Response(gzip);};
  try{
    const bytes=await loadSceneData('/optional',gzip.length,signal(),()=>{});
    bindModelSource('optional','/optional');
    assert.equal(entries.size,0,'completed downloads must not automatically persist');
    assert.deepEqual(modelCacheState('optional'),{downloaded:true,cached:false,pending:false});
    await setModelCached('optional',true);assert.equal(entries.size,1);
    await setModelCached('optional',false);assert.equal(entries.size,0);
    assert.equal(await loadSceneData('/optional',gzip.length,signal(),()=>{}),bytes);
    assert.equal(calls,1,'removing persistent storage must preserve decoded preview data');
    await setModelCached('optional',true);assert.equal(calls,1);
    assert.deepEqual(Buffer.from(await entries.get('/optional').clone().arrayBuffer()),gzip);
    for(const name of ['second','third']){
      await loadSceneData('/'+name,gzip.length,signal(),()=>{});bindModelSource(name,'/'+name);await setModelCached(name,true);
    }
    assert.equal(entries.size,3,'explicitly cached scenes must not be automatically evicted');
    await loadSceneData('/optional',gzip.length,signal(),()=>{});
    assert.equal(calls,3,'revisiting a cached scene must not download it again');
    entries.set('/corrupt',new Response(new Uint8Array(gzip.length)));
    assert.deepEqual(Buffer.from(await loadSceneData('/corrupt',gzip.length,signal(),()=>{})),original);
    assert.equal(calls,4);assert.equal(entries.has('/corrupt'),false);
  }finally{globalThis.fetch=fetcher;if(storage===undefined)delete globalThis.caches;else globalThis.caches=storage;}
});
