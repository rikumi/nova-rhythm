import type { LibraryMusic, MusicGroup } from './types';

interface StoryTrack {
  id?: string;
  name?: string;
  file: string;
  description?: string;
}
interface StoryGroup {
  id: string;
  name: string;
  date?: string;
  description?: string;
  outfit_references?: MusicGroup['outfit_references'];
  before_group?: string;
  tracks?: StoryTrack[];
}
export interface StoryMapping {
  schema_version: number;
  groups: StoryGroup[];
}
export interface StoryLibrary {
  groups: MusicGroup[];
  tracks: LibraryMusic[];
}

export function orderLibraryGroups(groups: MusicGroup[]): MusicGroup[] {
  const byId = new Map(groups.map(group => [group.id, group]));
  const result: MusicGroup[] = [], seen = new Set<string>(), visiting = new Set<string>();
  const emit = (group: MusicGroup) => {
    if (visiting.has(group.id)) throw new Error('分类排序关系存在循环');
    if (seen.has(group.id)) return;
    visiting.add(group.id);
    for (const child of groups.filter(candidate => candidate.before_group === group.id)) emit(child);
    visiting.delete(group.id); seen.add(group.id); result.push(group);
  };
  for (const group of [...groups].sort((a, b) => b.date.localeCompare(a.date))) {
    if (!group.before_group || !byId.has(group.before_group)) emit(group);
  }
  for (const group of groups) emit(group);
  return result;
}

/** The editable mapping controls membership, names, dates and display order. */
export function resolveStoryLibrary(mapping: StoryMapping, metadata: { tracks?: LibraryMusic[] }): StoryLibrary {
  if (mapping.schema_version !== 1 || !Array.isArray(mapping.groups)) throw new Error('故事旋律映射格式错误');
  const byFile = new Map((metadata.tracks || []).map(track => [track.path, track]));
  const groupIds = new Set<string>(), trackIds = new Set<string>(), files = new Set<string>();
  const tracks: LibraryMusic[] = [];
  const groups = mapping.groups.map(raw => {
    if (!raw.id || !raw.name || groupIds.has(raw.id)) throw new Error(`故事集编号缺失或重复：${raw.id || ''}`);
    if (raw.date && !/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(raw.date)) throw new Error(`故事集日期格式错误：${raw.name}`);
    groupIds.add(raw.id);
    const group: MusicGroup = { id: raw.id, name: raw.name, date: raw.date || '', description: raw.description, before_group: raw.before_group,
      track_ids: [], outfit_references: raw.outfit_references || [] };
    for (const entry of raw.tracks || []) {
      if (!entry.file || !(entry.file.startsWith('/') || entry.file.startsWith('https://')) || entry.file.startsWith('//') || entry.file.split('/').includes('..')) throw new Error(`音频文件路径错误：${entry.file || ''}`);
      const old = byFile.get(entry.file);
      const id = entry.id || old?.id || entry.file;
      if (trackIds.has(id) || files.has(entry.file)) throw new Error(`曲目重复收录：${entry.name || entry.file}`);
      trackIds.add(id); files.add(entry.file);
      const title = entry.name || entry.file.split('/').pop()?.replace(/\.[^.]+$/, '') || entry.file;
      tracks.push({ sample_rate: 44100, channels: 2, number_of_samples: 0, duration_seconds: 0, loop: null,
        source_title: title, route_ids: [], uses: [], aliases: [], ...old,
        id, title, path: entry.file, group_id: group.id, description: entry.description });
      group.track_ids.push(id);
    }
    return group;
  });
  return { groups: orderLibraryGroups(groups), tracks };
}
