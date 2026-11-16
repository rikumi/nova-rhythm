import assert from 'node:assert/strict';
import test from 'node:test';
import { nextPlaybackMode, nextQueueIndex } from '../../src/playbackMode.ts';

test('single repeat, queue repeat, shuffle and once have distinct modes', () => {
  assert.equal(nextPlaybackMode('single'), 'sequence');
  assert.equal(nextPlaybackMode('sequence'), 'shuffle');
  assert.equal(nextPlaybackMode('shuffle'), 'once');
  assert.equal(nextPlaybackMode('once'), 'single');
});
test('queue repeat wraps while shuffle excludes the currently playing track', () => {
  assert.equal(nextQueueIndex(3, 2, 1, 'sequence'), 0);
  assert.equal(nextQueueIndex(3, 0, -1, 'sequence'), 2);
  for (let current = 0; current < 4; current++) {
    const draws = [0, .4, .999].map(value => nextQueueIndex(4, current, 1, 'shuffle', () => value));
    assert.equal(new Set(draws).size, 3);
    assert.equal(draws.includes(current), false);
  }
  assert.equal(nextQueueIndex(1, 0, 1, 'shuffle'), 0);
  assert.equal(nextQueueIndex(0, -1, 1, 'shuffle'), -1);
});
