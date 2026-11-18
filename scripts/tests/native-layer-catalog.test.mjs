import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';

const read=path=>JSON.parse(readFileSync(new URL(path,import.meta.url),'utf8'));
const catalog=read('../../public/data/outfits.json').items;
const sharp=read('../../public/data/sharp-scenes.json').outfits;
const recovered=read('../../references/native-layer-recovery.json').outfits;
const audit=read('../../references/native-layer-recovery.json').audit;

test('4046 retains its original five-layer prefab instead of a generated 3D replacement',()=>{
  const item=catalog.find(item=>item.code==='4046');
  assert.deepEqual(item.card.layers.map(layer=>layer.name),[
    '4046_snow','4046_actor1','4046_rough','4046_title','4046_subtitle',
  ]);
  assert.equal(item.card.motion.rotation_y,-10);
  assert.equal(sharp['4046'],undefined);
});

test('recovered native artwork is complete and every native card is excluded from SHARP',()=>{
  for(const item of catalog){
    if(!item.card.layers.length)continue;
    assert.equal(sharp[item.code],undefined,`${item.code} must retain native layers`);
    for(const layer of item.card.layers){
      assert.ok(existsSync(new URL(`../../public${layer.path}`,import.meta.url)),`${item.code}: ${layer.path}`);
    }
  }
  for(const [code,result] of Object.entries(recovered)){
    assert.deepEqual(catalog.find(item=>item.code===code).card,result.card,`${code} recovery must survive regeneration`);
  }
});

test('all outfits are audited and special ImageWarp backgrounds and unprefixed sprites survive',()=>{
  assert.deepEqual(Object.keys(audit.outfits).sort(),catalog.map(item=>item.code).sort());
  assert.deepEqual(audit.unreadable_components,[]);
  assert.equal(audit.native_count,catalog.filter(item=>item.card.layers.length).length);
  const card=code=>catalog.find(item=>item.code===code).card;
  assert.ok(card('4043').layers.some(layer=>layer.name==='4043_bg'&&layer.branch==='layer_0'));
  assert.ok(card('4016').layers.some(layer=>layer.name==='bg'));
  assert.ok(card('4016').layers.some(layer=>layer.name==='01'));
  assert.equal(card('4012').layers.length,17);
});
