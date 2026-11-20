import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { nativeLoopRegion, loopPosition, hasLoopMarkers } from '../../src/audioLoop.ts';

test('Chunri Jishi uses original samples at the source rate for both melodies',()=>{
  const catalog=JSON.parse(readFileSync(new URL('../../public/data/outfits.json',import.meta.url),'utf8'));
  const tracks=catalog.items.find(item=>item.code==='4016').music;
  const core=nativeLoopRegion(tracks[0],tracks[0].duration_seconds);
  assert.equal(core.start,354461/48000);
  assert.equal(core.end,7443691/48000);
  assert.equal(loopPosition(0,core),0); // play intro on the first pass
  assert.equal(loopPosition(core.end,core),core.start);
  assert.ok(Math.abs(loopPosition(core.end+.25,core)-core.start-.25)<1e-9);
  assert.ok(Math.abs(loopPosition(core.end+(core.end-core.start)*3+.5,core)-core.start-.5)<1e-9);
  assert.equal(nativeLoopRegion(tracks[1],tracks[1].duration_seconds).start,353788/48000);
});

test('decoded duration clamps B and invalid loop data cannot create an empty cycle',()=>{
  const track={sample_rate:48000,loop:{start:48000,end:480000}};
  assert.deepEqual(nativeLoopRegion(track,8),{start:1,end:8});
  for(const loop of [null,{start:48000,end:48000},{start:-1,end:5000},{start:NaN,end:5000}])
    assert.equal(nativeLoopRegion({...track,loop},8),null);
  assert.equal(nativeLoopRegion({...track,sample_rate:0},8),null);
  assert.equal(nativeLoopRegion(track,.5),null);
});

test('layered mixer exposes its native shared loop and tracks without loops have no labels',()=>{
  assert.deepEqual(nativeLoopRegion({mixer:{loop_start:4}},32),{start:4,end:32});
  assert.equal(nativeLoopRegion({sample_rate:48000,loop:null},32),null);
});

test('whole-track loops have no labels, but skipping the intro or outro retains both labels',()=>{
  assert.equal(hasLoopMarkers({start:0,end:120},120),false);
  assert.equal(hasLoopMarkers({start:0,end:119.99998},120),false);
  assert.equal(hasLoopMarkers({start:8,end:120},120),true);
  assert.equal(hasLoopMarkers({start:0,end:119},120),true);
  assert.equal(hasLoopMarkers(null,120),false);
});
