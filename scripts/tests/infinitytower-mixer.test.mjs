import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { applyInfinityTowerMixer } from '../../src/infinitytowerMixer.ts';
import { libraryQueue } from '../../src/libraryNavigation.ts';

test('sixteen combinations become one playable entry while menu/boss tracks and old links survive',()=>{
  const definition=JSON.parse(readFileSync('public/data/infinitytower-mixer.json','utf8'));
  const variants=Object.keys(definition.combinations);
  assert.equal(variants.length,16);assert.equal(definition.streams.length,9);
  const library={tracks:[{id:'menu'},...variants.map(id=>({id,sample_rate:44100,path:'/audio/'+id+'.opus'})),{id:'boss'}],groups:[{id:'tower',track_ids:['menu',...variants,'boss']}]};
  const result=applyInfinityTowerMixer(library,definition);
  assert.deepEqual(result.groups[0].track_ids,['menu',definition.track_id,'boss']);
  assert.equal(result.tracks.find(t=>t.id===definition.track_id).legacy_ids.length,15);
  assert.equal(libraryQueue(result.groups,result.tracks).length,3);
  for(let row=0;row<4;row++) {
    const streams=definition.streams.filter(stream=>stream.row===row);
    assert.equal(streams.length,2);
    assert.equal(streams[0].cues[0].start,streams[1].cues[0].start);
    assert.equal(streams[0].cues[0].duration,streams[1].cues[0].duration);
  }
});
