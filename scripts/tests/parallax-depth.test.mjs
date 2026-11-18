import assert from 'node:assert/strict';
import test from 'node:test';
import {cardDepths} from '../../src/parallaxDepth.ts';
import {readFileSync} from 'node:fs';

test('native layers retain game depth, perspective and their original ratios',()=>{
  const card={mask_size:100,layers:[{native_z:200},{native_z:0},{native_z:-100,projection_factor:1.2}]};
  assert.deepEqual(cardDepths(card),[2,0,-1.2]);
  assert.deepEqual(cardDepths({...card,layers:card.layers.map(layer=>({...layer,native_z:layer.native_z*2}))}),[4,0,-2.4]);
});

test('all native cards use the prefab projection without subject insets or depth compression',()=>{
  const outfits=JSON.parse(readFileSync(new URL('../../public/data/outfits.json',import.meta.url),'utf8')).items;
  for(const outfit of outfits){
    const card=outfit.card;
    assert.deepEqual(cardDepths(card),card.layers.map(layer=>layer.native_z*layer.projection_factor/card.mask_size),outfit.name);
  }
});

test('empty cards and zero depth stay stationary',()=>{
  assert.deepEqual(cardDepths({layers:[]}),[]);
  assert.deepEqual(cardDepths({mask_size:100,layers:[{native_z:0},{native_z:10}]}),[0,.1]);
});
