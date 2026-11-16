export type PlaybackMode = 'single' | 'sequence' | 'shuffle' | 'once';
export const PLAYBACK_MODES: PlaybackMode[] = ['sequence', 'single', 'shuffle', 'once'];
export const MODE_LABELS: Record<PlaybackMode, string> = {
  single: '单曲循环', sequence: '顺序循环', shuffle: '随机播放', once: '播放一次',
};
export function nextPlaybackMode(mode: PlaybackMode): PlaybackMode {
  return PLAYBACK_MODES[(PLAYBACK_MODES.indexOf(mode) + 1) % PLAYBACK_MODES.length];
}
export function nextQueueIndex(length: number, current: number, direction: -1 | 1, mode: PlaybackMode, random = Math.random): number {
  if (!length) return -1;
  if (current < 0) return direction === 1 ? 0 : length - 1;
  if (mode === 'shuffle' && length > 1) {
    const other = Math.min(length - 2, Math.max(0, Math.floor(random() * (length - 1))));
    return other >= current ? other + 1 : other;
  }
  return (current + direction + length) % length;
}
