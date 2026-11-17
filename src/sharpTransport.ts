export interface SceneProgress {
  phase: 'download' | 'retry' | 'decompress' | 'parse';
  loaded?: number; total?: number; attempt?: number;
}

class DownloadFailure extends Error {
  readonly permanent: boolean;
  constructor(message: string, permanent = false) { super(message); this.permanent = permanent; }
}

export async function downloadScene(url: string, options: {
  signal: AbortSignal; total?: number; progress: (state: SceneProgress) => void;
  fetcher?: typeof fetch; idleMs?: number; retryDelayMs?: number;
}): Promise<Blob> {
  const {signal, progress, fetcher = fetch, idleMs = 45000, retryDelayMs = 500} = options;
  let chunks: Uint8Array<ArrayBuffer>[] = [], loaded = 0, total = options.total || 0;
  const retries = 3;
  for(let attempt = 0; attempt <= retries; attempt++) {
    signal.throwIfAborted();
    const controller = new AbortController();
    const abort = () => controller.abort(signal.reason);
    signal.addEventListener('abort', abort, {once: true});
    let activity = Date.now(), lastPercent = -1, reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    // Continuous slow transfers are allowed to finish. Only a stalled transfer
    // is timed out, and its next request resumes from the last received byte.
    const watchdog = setInterval(() => {
      if(Date.now() - activity >= idleMs) controller.abort(new Error('三维场景下载暂时中断'));
    }, Math.min(1000, idleMs));
    try {
      progress({phase: 'download', loaded, total});
      const response = await fetcher(url, {signal: controller.signal, cache: 'no-store',
        headers: loaded ? {Range: `bytes=${loaded}-`} : undefined});
      activity = Date.now();
      if(!response.ok || !response.body) {
        await response.body?.cancel();
        if(response.status === 416) { chunks = []; loaded = 0; }
        throw new DownloadFailure(`三维场景下载失败（${response.status}）`,
          response.status >= 400 && response.status < 500 && ![408, 416, 429].includes(response.status));
      }
      const range = response.headers.get('Content-Range')?.match(/^bytes (\d+)-(\d+)\/(\d+)$/);
      if(response.status === 206 && range && Number(range[1]) !== loaded)
        throw new DownloadFailure('三维场景续传位置不一致', true);
      if(response.status !== 206 && loaded) { chunks = []; loaded = 0; }
      total = options.total || (range ? Number(range[3]) : loaded + Number(response.headers.get('Content-Length') || 0));
      reader = response.body.getReader();
      while(true) {
        const {done, value} = await reader.read();
        if(done) break;
        activity = Date.now();
        chunks.push(value as Uint8Array<ArrayBuffer>); loaded += value.byteLength;
        if(total && loaded > total) throw new DownloadFailure('三维场景文件大小不一致', true);
        const percent = total ? Math.floor(loaded / total * 100) : Math.floor(loaded / 1048576);
        if(percent !== lastPercent) { progress({phase: 'download', loaded, total}); lastPercent = percent; }
      }
      if(total && loaded !== total) throw new DownloadFailure('三维场景下载未完成');
      return new Blob(chunks, {type: 'application/octet-stream'});
    } catch(error) {
      controller.abort();
      if(signal.aborted) throw signal.reason;
      if(!(error instanceof DownloadFailure && error.permanent) && total && loaded === total)
        return new Blob(chunks, {type: 'application/octet-stream'});
      if(error instanceof DownloadFailure && error.permanent || attempt === retries) throw error;
      progress({phase: 'retry', loaded, total, attempt: attempt + 1});
      signal.throwIfAborted();
      await new Promise<void>((resolve, reject) => {
        const cancelled = () => { clearTimeout(timer); reject(signal.reason); };
        const timer = setTimeout(() => { signal.removeEventListener('abort', cancelled); resolve(); }, retryDelayMs * (attempt + 1));
        signal.addEventListener('abort', cancelled, {once: true});
      });
    } finally {
      clearInterval(watchdog); reader?.releaseLock();
      signal.removeEventListener('abort', abort);
    }
  }
  throw new Error('三维场景下载失败');
}
