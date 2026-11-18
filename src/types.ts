import type { MixerDefinition } from './layeredAudio';
export interface Music {
  id: string;
  title: string;
  path: string;
  sample_rate: number;
  channels: number;
  number_of_samples: number;
  duration_seconds: number;
  loop: { start: number; end: number } | null;
  content_id?: string; shared_uses?: string[];
  display_title?: string;
  display_subtitle?: string;
  mixer?: MixerDefinition;
}
export interface MusicGroup {
  id: string; name: string; date: string; track_ids: string[];
  description?: string;
  before_group?: string;
  outfit_references?: { outfit_id: number; name: string; cover: string; content_ids: string[] }[];
}
export interface LibraryMusic extends Music {
  group_id: string; source_title: string; route_ids: string[];
  description?: string;
  legacy_ids?: string[];
  uses: string[]; aliases: string[];
}
export interface CardLayer {
  name: string; path: string; x: number; y: number;
  width: number; height: number; rotation: number;
  pivot: { x: number; y: number }; opacity: number;
  branch: string; is_title: boolean;
  native_z?: number; projection_factor?: number;
  blend_mode?: 'additive'; blend_source?: string;
}
export interface Skill { Id: number; Name: string; formatted_description: string; Level: number; }
export interface Outfit {
  id: number; code: string; name: string; storyTitle: string; story: string;
  literary: string; description: string; characters: string[];
  element: number; rarity: number; tags: string[];
  attributes: { name: string; value: string }[];
  cover: string; thumbnail: string; staticImage: string; fullCover?: string;
  card: { mask_size: number; layers: CardLayer[]; layout?: 'canvas'; motion?: { rotation_x: number; rotation_y: number }; camera?: { reference_resolution: [number, number]; vertical_fov: number; focal_length: number; plane_distance: number; source_sha256: string } };
  activity: { date: string; name: string; id: number; basis: string };
  music: Music[]; mainSkill: Skill | null; secondarySkills: Skill[];
}
