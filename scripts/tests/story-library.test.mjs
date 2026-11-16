import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { resolveStoryLibrary } from '../../src/storyLibrary.ts';

const load = name => JSON.parse(readFileSync(new URL(`../../public/data/${name}.json`, import.meta.url), 'utf8'));
const mapping = load('story-melodies');
const metadata = load('library');
const fixture = { schema_version: 1, groups: [
  { id: 'fixture-1', name: 'First', date: '2026-01-01', tracks: [{ name: 'Original', file: metadata.tracks[0].path }] },
  { id: 'fixture-2', name: 'Second', date: '', tracks: [] },
] };

test('editable mapping preserves the current reviewed library', () => {
  const result = resolveStoryLibrary(mapping, metadata);
  assert.equal(result.tracks.length, mapping.groups.reduce((n, g) => n+g.tracks.length, 0));
  const ordered = [...mapping.groups].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  assert.deepEqual(result.groups.map(g => g.id), ordered.map(g => g.id));
  for (const group of result.groups) {
    const entries = mapping.groups.find(g => g.id === group.id).tracks;
    assert.deepEqual(group.track_ids, entries.map(t => t.id || metadata.tracks.find(m => m.path === t.file)?.id || t.file));
  }
  for (const track of result.tracks) {
    const entry = mapping.groups.flatMap(g => g.tracks).find(t => t.file === track.path);
    const old = metadata.tracks.find(t => t.path === track.path);
    assert.equal(track.title, entry.name);
    assert.deepEqual(track.loop, old?.loop || null);
  }
});

test('single-file edits control addition, deletion, names, dates and descriptions', () => {
  const edited = structuredClone(fixture);
  const group = edited.groups[0];
  const removedFile = group.tracks.pop().file;
  group.name = '编辑后的故事集';
  group.date = '2030-01-01';
  group.description = '故事集说明';
  group.tracks.push({ name: '新增曲目', file: '/audio/new-song.opus', description: '曲目说明' });
  const result = resolveStoryLibrary(edited, metadata);
  assert.equal(result.groups[0].name, group.name);
  assert.equal(result.groups[0].date, group.date);
  assert.equal(result.groups[0].description, group.description);
  assert.equal(result.tracks.some(t => t.path === removedFile), false);
  const added = result.tracks.find(t => t.path === '/audio/new-song.opus');
  assert.equal(added.title, '新增曲目');
  assert.equal(added.description, '曲目说明');
  assert.equal(added.duration_seconds, 0); // The player learns this from decoded audio.
});

test('changed asset does not inherit another file’s loop parameters', () => {
  const edited = structuredClone(fixture);
  edited.groups[0].tracks[0].file = '/audio/replaced.opus';
  const changed = resolveStoryLibrary(edited, metadata).tracks.find(t => t.path === '/audio/replaced.opus');
  assert.equal(changed.loop, null);
  assert.equal(changed.id, '/audio/replaced.opus');
});

test('duplicate files and malformed dates produce actionable errors', () => {
  const duplicate = structuredClone(fixture);
  duplicate.groups[1].tracks.push(duplicate.groups[0].tracks[0]);
  assert.throws(() => resolveStoryLibrary(duplicate, metadata), /重复/);
  const invalid = structuredClone(fixture);
  invalid.groups[0].date = '2026/11/16';
  assert.throws(() => resolveStoryLibrary(invalid, metadata), /日期/);
});
