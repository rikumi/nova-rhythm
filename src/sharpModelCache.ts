const CACHE = 'nova-sharp-models-v1';
export interface ModelCacheState { downloaded: boolean; cached: boolean; pending: boolean; }
const EMPTY: ModelCacheState = {downloaded: false, cached: false, pending: false};
const states = new Map<string, ModelCacheState>(), sources = new Map<string, string>();
const listeners = new Set<() => void>();
let memory: {url: string; blob: Blob} | undefined;
function update(url: string, patch: Partial<ModelCacheState>) {
  states.set(url, {...(states.get(url) || EMPTY), ...patch}); listeners.forEach(listener => listener());
}
export function subscribeModelCache(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function modelCacheState(code: string): ModelCacheState { return states.get(sources.get(code) || '') || EMPTY; }
export function bindModelSource(code: string, url: string) {
  if(sources.get(code) !== url) { sources.set(code, url); listeners.forEach(listener => listener()); }
}
export function rememberModel(url: string, blob: Blob) {
  if(memory && memory.url !== url) update(memory.url, {downloaded: false});
  memory = {url, blob}; update(url, {downloaded: true});
}
export async function readModelCache(url: string, size?: number): Promise<Blob | undefined> {
  try {
    const cache = await caches.open(CACHE), response = await cache.match(url);
    if(response) {
      const blob = await response.blob();
      if(!size || blob.size === size) { update(url, {cached: true}); return blob; }
      await cache.delete(url);
    }
  } catch { /* Storage access is optional for previewing models. */ }
  update(url, {cached: false});
}
export async function discardModelCache(url: string): Promise<void> {
  await (await caches.open(CACHE)).delete(url); update(url, {cached: false});
}
export async function setModelCached(code: string, cached: boolean): Promise<void> {
  const url = sources.get(code);
  if(!url) throw new Error('模型尚未下载');
  update(url, {pending: true});
  try {
    if(cached) {
      const blob = memory?.url === url ? memory.blob : undefined;
      if(!blob) throw new Error('模型尚未下载');
      await (await caches.open(CACHE)).put(url, new Response(blob));
      update(url, {cached: true});
    } else await discardModelCache(url);
  } finally { update(url, {pending: false}); }
}
