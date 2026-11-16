import assert from 'node:assert/strict';
import test from 'node:test';
import { musicTitleParts } from '../../src/musicTitle.ts';

test('bracket content is the primary title and the prefix is a subtitle', () => {
  assert.deepEqual(musicTitleParts('正式曲名（原曲目名）'), { title: '原曲目名', subtitle: '正式曲名' });
  assert.deepEqual(musicTitleParts('正式曲名 (原曲目名)'), { title: '原曲目名', subtitle: '正式曲名' });
  assert.deepEqual(musicTitleParts('正式名 (伴奏)（原名（下））'), { title: '原名（下）', subtitle: '正式名 (伴奏)' });
  assert.deepEqual(musicTitleParts('普通曲名'), { title: '普通曲名' });
  assert.deepEqual(musicTitleParts('原名（未闭合'), { title: '原名（未闭合' });
});
