import assert from 'node:assert/strict';
import test from 'node:test';
import { cardDepths } from '../../src/parallaxDepth.ts';

test('native projection and original per-card depth spacing remain unnormalized',()=>{
  const card={mask_size:100,layers:[{name:'bg',native_z:200,projection_factor:2},
    {name:'person',native_z:50,projection_factor:3}]};
  assert.deepEqual(cardDepths(card),[4,1.32]);
  assert.deepEqual(cardDepths({...card,layers:card.layers.map(layer=>({...layer,native_z:layer.native_z*2}))}),[8,2.64]);
});
test('generated layers preserve their own canvas depth scale and projection',()=>{
  const card={layout:'canvas',mask_size:100,layers:[{native_z:400},{native_z:300},{native_z:100}]};
  assert.deepEqual(cardDepths(card),[4,3,1]);
});
