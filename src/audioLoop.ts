import type { Music } from './types';

export interface LoopRegion { start: number; end: number }

/** Sample positions belong to the source file's rate, not the AudioContext rate. */
export function nativeLoopRegion(track: Music | undefined, duration: number): LoopRegion | null {
  if (!track || !Number.isFinite(duration) || duration <= 0) return null;
  if (track.mixer) {
    const start = track.mixer.loop_start;
    return Number.isFinite(start) && start >= 0 && start < duration ? { start, end: duration } : null;
  }
  if (!track.loop || !Number.isFinite(track.sample_rate) || track.sample_rate <= 0) return null;
  const start = track.loop.start / track.sample_rate;
  const end = Math.min(duration, track.loop.end / track.sample_rate);
  return Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start ? { start, end } : null;
}

export function loopPosition(position: number, region: LoopRegion): number {
  return position >= region.end ? region.start + (position-region.start) % (region.end-region.start) : position;
}

/** Ignore sub-millisecond codec rounding at the end of a whole-track loop. */
export function hasLoopMarkers(region: LoopRegion | null, duration: number): boolean {
  return region !== null && (region.start > 0 || region.end < duration-.001);
}
