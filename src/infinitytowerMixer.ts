import type { MixerDefinition } from './layeredAudio';
import type { StoryLibrary } from './storyLibrary';

export function applyInfinityTowerMixer(library: StoryLibrary, definition?: MixerDefinition | null): StoryLibrary {
  if(!definition)return library;
  const canonical=library.tracks.find(track=>track.id===definition.track_id);
  if(!canonical)return library;
  const ids=new Set(Object.keys(definition.combinations));ids.add(definition.track_id);
  const track={...canonical,mixer:definition,legacy_ids:[...new Set([...(canonical.legacy_ids||[]),...ids])].filter(id=>id!==canonical.id),
    duration_seconds:definition.duration,number_of_samples:Math.round(definition.duration*canonical.sample_rate),
    loop:{start:Math.round(definition.loop_start*canonical.sample_rate),end:Math.round(definition.duration*canonical.sample_rate)}};
  return {tracks:library.tracks.flatMap(old=>old.id===track.id ? [track] : ids.has(old.id) ? [] : [old]),
    groups:library.groups.map(group=>{
      let inserted=false;
      return {...group,track_ids:group.track_ids.flatMap(id=>{
        if(!ids.has(id))return [id];
        if(inserted)return [];
        inserted=true;return [track.id];
      })};
    })};
}
