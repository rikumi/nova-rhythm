import { downloadScene } from './sharpTransport.ts';
import type { SceneProgress } from './sharpTransport';
import { readModelCache, rememberModel, discardModelCache } from './sharpModelCache.ts';

let decoded: {url: string; bytes: ArrayBuffer} | undefined;
interface Job {
  controller: AbortController; listeners: Set<(state: SceneProgress) => void>;
  promise: Promise<ArrayBuffer>; settled: boolean; state?: SceneProgress;
}
const jobs = new Map<string, Job>();

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
  progress: (state: SceneProgress) => void, gzip = true): Promise<ArrayBuffer> {
  signal.throwIfAborted();
  if(decoded?.url === url) { progress({phase: 'parse'}); return decoded.bytes; }
  let job = jobs.get(url);
  if(!job) {
    const controller = new AbortController(), listeners = new Set<(state: SceneProgress) => void>();
    const entry = {controller, listeners, settled: false} as Job;
    const report = (state: SceneProgress) => { entry.state = state; listeners.forEach(listener => listener(state)); };
    entry.promise = (async () => {
      let blob = await readModelCache(url, total);
      controller.signal.throwIfAborted();
      const fromCache = !!blob;
      blob ??= await downloadScene(url, {signal: controller.signal, total, progress: report});
      report({phase: 'decompress'});
      let bytes: ArrayBuffer;
      try { bytes = gzip ? await decompress(blob, controller.signal) : await blob.arrayBuffer(); }
      catch(error) {
        if(controller.signal.aborted || !fromCache) throw error;
        // A truncated/corrupt disk cache must recover without poisoning future visits.
        try { await discardModelCache(url); } catch { /* optional */ }
        blob = await downloadScene(url, {signal: controller.signal, total, progress: report});
        report({phase: 'decompress'}); bytes = gzip ? await decompress(blob, controller.signal) : await blob.arrayBuffer();
      }
      controller.signal.throwIfAborted();
      decoded = {url, bytes};
      rememberModel(url, blob);
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
