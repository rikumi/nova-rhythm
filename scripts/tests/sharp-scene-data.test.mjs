import assert from 'node:assert/strict';
import test from 'node:test';
import {gzipSync} from 'node:zlib';
import {loadSceneData} from '../../src/sharpSceneData.ts';

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

test('disk cache recovers corruption and stays bounded to two complete scenes',async()=>{
  const fetcher=globalThis.fetch,storage=globalThis.caches,entries=new Map();let calls=0;
  const cache={match:async key=>entries.get(key)?.clone(),put:async(key,response)=>{entries.set(key,response.clone());},
    keys:async()=>[...entries.keys()],delete:async key=>entries.delete(key)};
  globalThis.caches={open:async()=>cache};
  globalThis.fetch=async()=>{calls++;return new Response(gzip);};
  try{
    entries.set('/corrupt',new Response(new Uint8Array(gzip.length)));
    assert.deepEqual(Buffer.from(await loadSceneData('/corrupt',gzip.length,signal(),()=>{})),original);
    assert.equal(calls,1);
    await loadSceneData('/second',gzip.length,signal(),()=>{});
    await loadSceneData('/corrupt',gzip.length,signal(),()=>{});
    assert.equal(calls,2,'returning to a cached scene must not download again');
    await loadSceneData('/third',gzip.length,signal(),()=>{});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(entries.size,2);
  }finally{globalThis.fetch=fetcher;if(storage===undefined)delete globalThis.caches;else globalThis.caches=storage;}
});
