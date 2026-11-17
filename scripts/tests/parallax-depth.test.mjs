import assert from 'node:assert/strict';
import test from 'node:test';
import { cardDepths, MAX_NATIVE_PARALLAX } from '../../src/parallaxDepth.ts';
import { readFileSync } from 'node:fs';

test('native layers below the cap retain their original depths',()=>{
  const card={mask_size:100,layers:[{name:'bg',native_z:20},
    {name:'person',native_z:5}]};
  const depths=cardDepths(card);
  assert.equal(depths[0],.2);
  assert.ok(Math.abs(depths[1]-.044)<1e-12);
});
test('deep native cards preserve spacing ratios and zero while limiting both axes',()=>{
  const card={mask_size:100,motion:{rotation_x:30,rotation_y:-20},layers:[
    {name:'bg',native_z:200},{name:'person',native_z:0},{name:'front',native_z:-100}]};
  const depths=cardDepths(card),span=Math.max(...depths)-Math.min(...depths);
  assert.equal(depths[1],0);
  assert.ok(Math.abs(depths[0]/depths[2] - 2/-.88)<1e-12);
  assert.ok(span*Math.sin(Math.PI/6)<=MAX_NATIVE_PARALLAX.y+1e-12);
  assert.ok(span*Math.sin(Math.PI/9)<=MAX_NATIVE_PARALLAX.x+1e-12);
  assert.deepEqual(cardDepths({...card,layers:card.layers.map(layer=>({...layer,native_z:layer.native_z*2}))}),depths);
});
test('every native multi-layer outfit respects the calibrated SHARP motion limits',()=>{
  const outfits=JSON.parse(readFileSync(new URL('../../public/data/outfits.json',import.meta.url),'utf8')).items;
  for(const outfit of outfits){
    const card=outfit.card;if(card.layout==='canvas'||card.layers.length<2)continue;
    const depths=cardDepths(card),span=Math.max(...depths)-Math.min(...depths);
    const motion=card.motion||{rotation_x:3,rotation_y:-8};
    assert.ok(span*Math.abs(Math.sin(motion.rotation_y*Math.PI/180))<=MAX_NATIVE_PARALLAX.x+1e-12,outfit.name);
    assert.ok(span*Math.abs(Math.sin(motion.rotation_x*Math.PI/180))<=MAX_NATIVE_PARALLAX.y+1e-12,outfit.name);
  }
});
test('empty, coincident and static native cards do not acquire extra motion',()=>{
  assert.deepEqual(cardDepths({layers:[]}),[]);
  assert.deepEqual(cardDepths({mask_size:100,layers:[{native_z:10},{native_z:10/.88}]}),[.1,.1]);
  assert.deepEqual(cardDepths({mask_size:100,motion:{rotation_x:0,rotation_y:0},layers:[{native_z:500},{native_z:0}]}),[5,0]);
});
test('generated layers preserve their own canvas depth scale and projection',()=>{
  const card={layout:'canvas',mask_size:100,layers:[{native_z:400},{native_z:300},{native_z:100}]};
  assert.deepEqual(cardDepths(card),[4,3,1]);
});
