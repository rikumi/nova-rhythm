import assert from 'node:assert/strict';
import test from 'node:test';
import { loadOutfits } from '../../src/experimentalLayering.ts';
import { musicUrl } from '../../src/musicRoutes.ts';

const flat={code:'4016',card:{mask_size:712,layers:[]}};
const native={code:'4069',card:{mask_size:712,layers:[{path:'/native.webp'}]}};
const card={layout:'canvas',layers:Array.from({length:4},(_,i)=>({path:`/layer-${i}.webp`}))};
function server(manifest){
  const requests=[];
  return {requests,fetch:async path=>{
    requests.push(path);
    if(path==='/data/outfits.json')return Response.json({schemaVersion:1,items:[flat,native]});
    return manifest===null?new Response('',{status:404}):Response.json(manifest);
  }};
}
test('experimental artwork is opt-in and does not even fetch its manifest by default',async()=>{
  for(const suffix of ['', '?experimental_layering=0','?experimental_layering=true']){
    const api=server({schemaVersion:1,outfits:{'4016':card}});
    const result=await loadOutfits('https://example.com/'+suffix,api.fetch);
    assert.deepEqual(result.items[0],flat);assert.equal(api.requests.length,1);
  }
});
test('opt-in replaces only static cards; normal navigation preserves the parameter',async()=>{
  const api=server({schemaVersion:1,outfits:{'4016':card,'4069':card}});
  const href='https://example.com/?experimental_layering=1';
  const result=await loadOutfits(href,api.fetch);
  assert.equal(result.items[0].card.layers.length,4);assert.equal(result.items[0].card.layout,'canvas');
  assert.deepEqual(result.items[1],native);assert.equal(flat.card.layers.length,0);
  assert.equal(musicUrl(href,'next').searchParams.get('experimental_layering'),'1');
});
test('unavailable or incomplete experimental manifests retain the original artwork',async()=>{
  for(const manifest of [null,{}, {schemaVersion:1,outfits:{'4016':{...card,layers:card.layers.slice(0,3)}}}]){
    const api=server(manifest);const result=await loadOutfits('https://example.com/?experimental_layering=1',api.fetch);
    assert.deepEqual(result.items[0],flat);
  }
});
