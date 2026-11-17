import { downloadScene } from './sharpTransport.ts';
import type { SceneProgress } from './sharpTransport';

const CACHE = 'nova-sharp-models-v1';
let decoded: {url: string; bytes: ArrayBuffer} | undefined;
interface Job {
  controller: AbortController; listeners: Set<(state: SceneProgress) => void>;
  promise: Promise<ArrayBuffer>; settled: boolean; state?: SceneProgress;
}
const jobs = new Map<string, Job>();

async function cachedBlob(url: string, size?: number): Promise<Blob | undefined> {
  try {
    const response = await (await caches.open(CACHE)).match(url);
    if(response) {
      const blob = await response.blob();
      if(!size || blob.size === size) return blob;
      await (await caches.open(CACHE)).delete(url);
    }
  } catch { /* Storage may be disabled or full. Network loading remains available. */ }
}

async function storeBlob(url: string, blob: Blob): Promise<void> {
  try {
    const cache = await caches.open(CACHE);
    await cache.put(url, new Response(blob));
    const keys = await cache.keys();
    await Promise.all(keys.slice(0, Math.max(0, keys.length - 2)).map(key => cache.delete(key)));
  } catch { /* An optional cache must not prevent rendering. */ }
}

function decompress(blob: Blob, signal: AbortSignal): Promise<ArrayBuffer> {
  signal.throwIfAborted();
  if(typeof Worker === 'undefined')
    return new Response(blob.stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./sharpDecompress.worker.ts', import.meta.url), {type: 'module'});
    const finish = () => { worker.terminate(); signal.removeEventListener('abort', abort); };
    const abort = () => { finish(); reject(signal.reason); };
    signal.addEventListener('abort', abort, {once: true});
    worker.onmessage = event => {
      finish();
      if(event.data.error) reject(new Error(event.data.error)); else resolve(event.data.bytes);
    };
    worker.onerror = event => { finish(); reject(new Error(event.message || '三维场景解压失败')); };
    worker.postMessage({blob});
  });
}

export async function loadSceneData(url: string, total: number | undefined, signal: AbortSignal,
  progress: (state: SceneProgress) => void): Promise<ArrayBuffer> {
  signal.throwIfAborted();
  if(decoded?.url === url) { progress({phase: 'parse'}); return decoded.bytes; }
  let job = jobs.get(url);
  if(!job) {
    const controller = new AbortController(), listeners = new Set<(state: SceneProgress) => void>();
    const entry = {controller, listeners, settled: false} as Job;
    const report = (state: SceneProgress) => { entry.state = state; listeners.forEach(listener => listener(state)); };
    entry.promise = (async () => {
      let blob = await cachedBlob(url, total);
      controller.signal.throwIfAborted();
      const fromCache = !!blob;
      let needsStore = !fromCache;
      blob ??= await downloadScene(url, {signal: controller.signal, total, progress: report});
      report({phase: 'decompress'});
      let bytes: ArrayBuffer;
      try { bytes = await decompress(blob, controller.signal); }
      catch(error) {
        if(controller.signal.aborted || !fromCache) throw error;
        // A truncated/corrupt disk cache must recover without poisoning future visits.
        try { await (await caches.open(CACHE)).delete(url); } catch { /* optional */ }
        blob = await downloadScene(url, {signal: controller.signal, total, progress: report});
        needsStore = true;
        report({phase: 'decompress'}); bytes = await decompress(blob, controller.signal);
      }
      controller.signal.throwIfAborted();
      decoded = {url, bytes};
      if(needsStore)void storeBlob(url, blob);
      report({phase: 'parse'});
      return bytes;
    })();
    entry.promise.then(() => { entry.settled = true; if(jobs.get(url) === entry) jobs.delete(url); },
      () => { entry.settled = true; if(jobs.get(url) === entry) jobs.delete(url); });
    jobs.set(url, entry); job = entry;
  }
  const shared = job;
  const listener = (state: SceneProgress) => progress(state);
  shared.listeners.add(listener);
  if(shared.state) progress(shared.state);
  return new Promise<ArrayBuffer>((resolve, reject) => {
    const finish = () => {
      signal.removeEventListener('abort', abort); shared.listeners.delete(listener);
      if(!shared.settled && !shared.listeners.size) {
        shared.controller.abort();
        if(jobs.get(url) === shared) jobs.delete(url);
      }
    };
    const abort = () => { finish(); reject(signal.reason); };
    signal.addEventListener('abort', abort, {once: true});
    shared.promise.then(bytes => { finish(); resolve(bytes); }, error => { finish(); reject(error); });
  });
}
