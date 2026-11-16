import assert from 'node:assert/strict';
import test from 'node:test';
import { collectMusicPages,renderMusicPage } from '../build_music_pages.mjs';
import { musicPath,musicIdFromPath,outfitMusicPage } from '../../src/musicRoutes.ts';
test('outfit sharing uses its activity as the collection and a local JPEG preview',()=>{
  const page=outfitMusicPage({id:214062,name:'美好，尽在昨日',staticImage:'https://example.com/full.png',thumbnail:'/art/4062/thumb.webp',activity:{id:10112,name:'遥远的塔'}},
    {id:'audio-test',title:'核心旋律',path:'/audio/test.opus',duration_seconds:100},0);
  assert.equal(page.title,'美好，尽在昨日');assert.equal(page.collection,'遥远的塔');
  assert.equal(page.image,'/art/4062/preview.jpg');assert.equal(page.imageType,'image/jpeg');
  const html=renderMusicPage('<head><title>星塔旋律</title><meta name="description" content="old" /></head>',page,'https://xtxl.rkm.mx');
  assert.match(html,/property="og:description" content="星塔旋律 · 遥远的塔"/);
  assert.ok(!html.includes('https://example.com/full.png'));
});
test('path IDs round trip, including filenames unsafe as directory names',()=>{
  for(const id of ['audio-abc','/audio/自定义 + 曲目.opus','name?x=<>&'])assert.equal(musicIdFromPath(musicPath(id)),id);
  assert.equal(musicIdFromPath('/'),undefined);
});
test('static pages contain escaped metadata and direct audio without running JavaScript',()=>{
  const page={id:'audio-test',kind:'library',title:'曲目 <x> "标题"',collection:'故事 & 章节',audio:'/audio/test.opus',duration:62.5,image:'/icons/icon-512.png'};
  const html=renderMusicPage('<head><title>星塔旋律</title><meta name="description" content="old" /></head>',page,'https://xtxl.rkm.mx');
  assert.match(html,/property="og:title" content="曲目 &lt;x&gt; &quot;标题&quot;"/);
  assert.match(html,/property="og:description" content="星塔旋律 · 故事 &amp; 章节"/);
  assert.match(html,/property="og:audio" content="https:\/\/xtxl.rkm.mx\/audio\/test.opus"/);
  assert.match(html,/property="og:audio:type" content="audio\/ogg"/);
  assert.match(html,/"contentUrl":"https:\/\/xtxl.rkm.mx\/audio\/test.opus"/);
  assert.match(html,/"duration":"PT62.5S"/);
  assert.ok(!html.includes('<x>'));
});
