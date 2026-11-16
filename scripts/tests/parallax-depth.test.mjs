import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizedDepthTarget,normalizedDepths,DEPTH_SPAN_GAIN } from '../../src/parallaxDepth.ts';

const layer=(z,name='object')=>({name,native_z:z,projection_factor:1});
const card=layers=>({mask_size:100,layers});
test('all cards share a span 10% below the native average while internal depth ratios survive',()=>{
  const first=card([layer(100,'bg'),layer(50),layer(0)]),second=card([layer(200,'bg'),layer(0)]);
  const target=normalizedDepthTarget([{card:first},{card:second}]);
  assert.ok(Math.abs(target-1.5*DEPTH_SPAN_GAIN)<1e-12);
  for(const c of [first,second]){
    const depths=normalizedDepths(c,target);
    assert.ok(Math.abs(Math.max(...depths)-Math.min(...depths)-target)<1e-12);
  }
  const depths=normalizedDepths(first,target);
  assert.ok(Math.abs((depths[1]-depths[2])/(depths[0]-depths[2])-.44)<1e-12);
});
test('generated cards are normalized too, and do not affect the native baseline',()=>{
  const native=card([layer(100,'bg'),layer(0)]),generated={...card([layer(400),layer(300),layer(200),layer(100)]),layout:'canvas'};
  const target=normalizedDepthTarget([{card:native},{card:generated}]);
  assert.equal(target,DEPTH_SPAN_GAIN);
  const depths=normalizedDepths(generated,target);
  assert.ok(Math.abs(depths[0]-depths[3]-target)<1e-12);
  assert.ok(Math.abs(depths[0]-depths[1]-(depths[1]-depths[2]))<1e-12);
  assert.deepEqual(normalizedDepths(card([layer(100)]),target),[0]);
});
