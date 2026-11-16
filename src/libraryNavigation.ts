import type { LibraryMusic, MusicGroup } from './types';
import { musicUrl } from './musicRoutes.ts';

export function libraryTrackUrl(href: string, trackId: string): URL {
  return musicUrl(href,trackId);
}

/** Outfit references are navigation links, never entries in the playback queue. */
export function libraryQueue(groups: MusicGroup[], tracks: LibraryMusic[]): LibraryMusic[] {
  const byId = new Map(tracks.map(track => [track.id, track]));
  return groups.flatMap(group => group.track_ids.flatMap(id => {
    const track = byId.get(id);
    return track ? [track] : [];
  }));
}

export function adjacentLibraryTrack(queue: LibraryMusic[], currentId: string, direction: -1 | 1): LibraryMusic | undefined {
  if (!queue.length) return;
  const index = queue.findIndex(track => track.id === currentId);
  if (index < 0) return direction === 1 ? queue[0] : queue[queue.length-1];
  return queue[(index+direction+queue.length) % queue.length];
}
