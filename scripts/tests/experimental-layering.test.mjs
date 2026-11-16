import assert from 'node:assert/strict';
import test from 'node:test';
import { loadOutfits, loadGeneratedCards } from '../../src/experimentalLayering.ts';
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
test('catalog stays original and generated cards load separately for the persistent toggle',async()=>{
  const api=server({schemaVersion:1,outfits:{'4016':card,'4069':card}});
  const href='https://example.com/?experimental_layering=1';
  const result=await loadOutfits(href,api.fetch);
  assert.deepEqual(result.items[0],flat);
  const generated=await loadGeneratedCards(api.fetch);
  assert.equal(generated['4016'].layers.length,4);assert.equal(generated['4016'].layout,'canvas');
  assert.deepEqual(result.items[1],native);assert.equal(flat.card.layers.length,0);
  assert.equal(musicUrl(href,'next').searchParams.get('experimental_layering'),'1');
});
test('unavailable or incomplete experimental manifests retain the original artwork',async()=>{
  for(const manifest of [null,{}, {schemaVersion:1,outfits:{'4016':{...card,layers:card.layers.slice(0,1)}}}]){
    const api=server(manifest);const result=await loadOutfits('https://example.com/?experimental_layering=1',api.fetch);
    assert.deepEqual(result.items[0],flat);
    assert.deepEqual(await loadGeneratedCards(api.fetch),{});
  }
});
test('reviewed corrections may use fewer layers to keep complete figures together',async()=>{
  const corrected={...card,layers:card.layers.slice(0,2)};
  const api=server({schemaVersion:1,outfits:{'4016':corrected}});
  assert.deepEqual((await loadGeneratedCards(api.fetch))['4016'],corrected);
});
