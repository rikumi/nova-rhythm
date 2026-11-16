import assert from 'node:assert/strict';
import test from 'node:test';
import { adjacentLibraryTrack, libraryQueue, libraryTrackUrl } from '../../src/libraryNavigation.ts';
import { orderLibraryGroups, libraryGroupLabel } from '../../src/storyLibrary.ts';

test('group labels follow prefixes and treat mainline-update activities as mainline', () => {
  assert.equal(libraryGroupLabel('activity-123'), '活动');
  assert.equal(libraryGroupLabel('activity-123', '主线更新剧情：角色'), '主线');
  assert.equal(libraryGroupLabel('activity-123', '限时活动剧情：角色'), '活动');
  assert.equal(libraryGroupLabel('mainline-5'), '主线');
  assert.equal(libraryGroupLabel('story-one'), '故事');
  assert.equal(libraryGroupLabel('mode-one'), '模式');
  assert.equal(libraryGroupLabel('permanent-combat'), undefined);
});

test('share link identifies a story track and clears outfit navigation', () => {
  const url = libraryTrackUrl('https://xtxl.rkm.mx/?disc=214001#/outfit', 'audio-one');
  assert.equal(url.searchParams.get('track'), 'audio-one');
  assert.equal(url.searchParams.has('disc'), false);
  assert.equal(url.hash, '#/library');
  assert.equal(libraryTrackUrl('https://xtxl.rkm.mx/', '/audio/自定义 + 曲目.opus').searchParams.get('track'), '/audio/自定义 + 曲目.opus');
});

test('permanent gameplay anchors override dates without changing stored dates', () => {
  const groups = [
    { id: 'new-event', date: '2030-01-01' }, { id: 'first-mode', date: '2040-01-01', before_group: 'permanent-combat' },
    { id: 'second-mode', date: '', before_group: 'permanent-combat' }, { id: 'system', date: '' },
    { id: 'permanent-combat', date: '' }, { id: 'tail', date: '' },
  ];
  assert.deepEqual(orderLibraryGroups(groups).map(g => g.id), ['new-event', 'system', 'first-mode', 'second-mode', 'permanent-combat', 'tail']);
  assert.equal(groups[1].date, '2040-01-01');
  assert.throws(() => orderLibraryGroups([{ id: 'a', date: '', before_group: 'b' }, { id: 'b', date: '', before_group: 'a' }]), /循环/);
});

test('previous and next preserve group order, wrap, and skip all outfit references', () => {
  const groups = [
    { id: 'first', track_ids: ['one', 'two'], outfit_references: [{ outfit_id: 123, content_ids: ['outfit-music'] }] },
    { id: 'outfits-only', track_ids: [], outfit_references: [{ outfit_id: 456, content_ids: ['outfit-music'] }] },
    { id: 'last', track_ids: ['three'] },
  ];
  const tracks = [{ id: 'three' }, { id: 'one' }, { id: 'two' }];
  const queue = libraryQueue(groups, tracks);
  assert.deepEqual(queue.map(t => t.id), ['one', 'two', 'three']);
  assert.equal(adjacentLibraryTrack(queue, 'two', 1).id, 'three');
  assert.equal(adjacentLibraryTrack(queue, 'one', -1).id, 'three');
  assert.equal(adjacentLibraryTrack(queue, 'three', 1).id, 'one');
  assert.equal(adjacentLibraryTrack([], 'missing', 1), undefined);
});
