import type { Music } from './types';
import { PLAYBACK_MODES, type PlaybackMode } from './playbackMode';

export interface Playback {
  trackId: string; playing: boolean; loading: boolean; error: string;
  position: number; duration: number; volume: number; loop: boolean; mode: PlaybackMode; peaks: number[];
}

/** Uses the original sample loop boundaries; the intro is played only once. */
class Player {
  private context?: AudioContext;
  private musicGain?: GainNode;
  private source?: AudioBufferSourceNode;
  private sourceGain?: GainNode;
  private buffer?: AudioBuffer;
  private track?: Music;
  private startedAt = 0;
  private offset = 0;
  private generation = 0;
  private abort?: AbortController;
  private listeners = new Set<() => void>();
  private endedListeners = new Set<(trackId: string) => void>();
  private cache = new Map<string, AudioBuffer>();
  private sounds = new Map<string, Promise<AudioBuffer>>();
  private lastSound = 0;
  private value: Playback = {
    trackId: '', playing: false, loading: false, error: '', position: 0,
    duration: 0, volume: .65, loop: true, mode: 'single', peaks: [],
  };

  constructor() {
    try { const mode = localStorage.getItem('nova-playback-mode') as PlaybackMode; if (PLAYBACK_MODES.includes(mode)) { this.value.mode = mode; this.value.loop = mode === 'single'; } } catch { /* optional */ }
    try { const v = Number(localStorage.getItem('nova-volume')); if (localStorage.getItem('nova-volume') !== null && Number.isFinite(v)) this.value.volume = Math.max(0, Math.min(1, v)); } catch { /* storage is optional */ }
    setInterval(() => { if (this.value.playing) this.update({ position: this.position() }); }, 100);
  }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  subscribeEnded = (listener: (trackId: string) => void) => { this.endedListeners.add(listener); return () => { this.endedListeners.delete(listener); }; };
  snapshot = () => this.value;
  private update(patch: Partial<Playback>) {
    this.value = { ...this.value, ...patch };
    this.listeners.forEach(fn => fn());
  }
  private getContext() {
    if (!this.context) {
      this.context = new AudioContext();
      this.musicGain = this.context.createGain();
      this.musicGain.gain.value = this.value.volume;
      this.musicGain.connect(this.context.destination);
    }
    return this.context;
  }
  private async ready() {
    const context = this.getContext();
    if (context.state === 'suspended') await context.resume();
    return context;
  }
  async selectFromLink(track: Music) {
    await this.select(track);
    if (this.value.playing) return true;
    const context = this.getContext();
    // A cold mobile/browser tab may require a gesture. Leave a usable play
    // button rather than hanging in loading while resume() waits for permission.
    if (context.state !== 'running' && !navigator.userActivation?.hasBeenActive) return false;
    await this.play();
    return this.value.playing;
  }
  private stopSource() {
    const source = this.source; const gain = this.sourceGain;
    if (!source || !this.context) return;
    source.onended = null;
    const now = this.context.currentTime;
    gain?.gain.cancelScheduledValues(now);
    gain?.gain.setValueAtTime(gain.gain.value, now);
    gain?.gain.linearRampToValueAtTime(0, now + .045);
    try { source.stop(now + .05); } catch { /* already ended */ }
    setTimeout(() => { source.disconnect(); gain?.disconnect(); }, 70);
    this.source = undefined;
  }
  private boundaries() {
    const rate = this.track?.sample_rate || 44100;
    const duration = this.buffer?.duration || this.value.duration;
    const start = Math.max(0, (this.track?.loop?.start || 0) / rate);
    const end = Math.min(duration, (this.track?.loop?.end || duration * rate) / rate);
    return { start, end: end > start ? end : duration };
  }
  private position() {
    let position = this.offset + (this.context ? this.context.currentTime - this.startedAt : 0);
    const { start, end } = this.boundaries();
    if (this.value.loop && end > start && position >= end) position = start + ((position - start) % (end - start));
    return Math.min(position, this.value.duration);
  }
  async select(track: Music, autoplay = false) {
    if (this.track?.id === track.id) { if (autoplay && !this.value.playing && !this.value.loading) await this.play(); return; }
    const generation = ++this.generation;
    this.abort?.abort(); this.stopSource();
    this.track = track; this.buffer = undefined; this.offset = 0;
    this.update({ trackId: track.id, playing: false, loading: false, error: '', position: 0, duration: track.duration_seconds, peaks: [] });
    // Avoid downloading a large music file before the first user interaction.
    if (!autoplay) return;
    await this.loadAndPlay(generation);
  }
  private async loadAndPlay(generation: number) {
    if (!this.track) return;
    this.update({ loading: true, error: '' });
    const track = this.track;
    try {
      const context = await this.ready();
      let buffer = this.cache.get(track.path);
      if (!buffer) {
        this.abort = new AbortController();
        const response = await fetch(encodeURI(track.path), { signal: this.abort.signal });
        if (!response.ok) throw new Error(`音频读取失败（${response.status}）`);
        buffer = await context.decodeAudioData(await response.arrayBuffer());
        if (generation !== this.generation) return;
        this.cache.set(track.path, buffer);
        if (this.cache.size > 3) this.cache.delete(this.cache.keys().next().value!);
      }
      if (generation !== this.generation) return;
      this.buffer = buffer;
      const samples = buffer.getChannelData(0); const peaks: number[] = [];
      for (let i = 0; i < 70; i++) {
        const start = Math.floor(samples.length * i / 70); const stop = Math.floor(samples.length * (i + 1) / 70);
        let sum = 0; let n = 0;
        for (let j = start; j < stop; j += 32) { sum += samples[j] ** 2; n++; }
        peaks.push(Math.sqrt(sum / Math.max(n, 1)));
      }
      const max = Math.max(...peaks, .001);
      this.update({ duration: buffer.duration, loading: false, peaks: peaks.map(v => v / max) });
      this.start();
    } catch (error) {
      if (generation !== this.generation || (error as Error).name === 'AbortError') return;
      this.update({ loading: false, playing: false, error: (error as Error).message || '音频暂时无法播放，请重试' });
    }
  }
  private start() {
    if (!this.buffer || !this.context || !this.musicGain) return;
    this.stopSource();
    const source = this.context.createBufferSource(); const gain = this.context.createGain();
    source.buffer = this.buffer; source.loop = this.value.loop;
    const { start, end } = this.boundaries(); source.loopStart = start; source.loopEnd = end;
    gain.gain.setValueAtTime(0, this.context.currentTime);
    gain.gain.linearRampToValueAtTime(1, this.context.currentTime + .06);
    source.connect(gain); gain.connect(this.musicGain);
    this.offset = Math.min(this.offset, Math.max(0, this.buffer.duration - .001));
    this.startedAt = this.context.currentTime;
    this.source = source; this.sourceGain = gain;
    source.onended = () => {
      if (this.source === source && !source.loop) {
        this.offset = 0; this.source = undefined;
        this.update({ playing: false, position: 0 });
        if (this.value.mode === 'sequence' || this.value.mode === 'shuffle') this.endedListeners.forEach(listener => listener(this.value.trackId));
      }
      source.disconnect(); gain.disconnect();
    };
    source.start(0, this.offset);
    this.update({ playing: true });
  }
  async play() {
    if (!this.track || this.value.loading) return;
    if (!this.buffer) { await this.loadAndPlay(this.generation); return; }
    await this.ready(); this.start();
  }
  pause() {
    if (!this.value.playing) return;
    this.offset = this.position(); this.stopSource();
    this.update({ playing: false, position: this.offset });
  }
  toggle = async () => { if (this.value.playing) this.pause(); else await this.play(); };
  seek(seconds: number) {
    this.offset = Math.max(0, Math.min(seconds, Math.max(0, this.value.duration - .001)));
    if (this.value.playing) this.start();
    this.update({ position: this.offset });
  }
  setVolume(volume: number) {
    this.update({ volume });
    if (this.context && this.musicGain) this.musicGain.gain.setTargetAtTime(volume, this.context.currentTime, .03);
    try { localStorage.setItem('nova-volume', String(volume)); } catch { /* optional */ }
  }
  toggleLoop() {
    this.setMode(this.value.loop ? 'once' : 'single');
  }
  setMode(mode: PlaybackMode) {
    // Capture the wrapped sample position before changing native loop behavior.
    const position = this.value.playing ? this.position() : this.offset;
    const playing = this.value.playing;
    this.offset = position;
    this.update({ mode, loop: mode === 'single' });
    if (playing) this.start();
    try { localStorage.setItem('nova-playback-mode', mode); } catch { /* optional */ }
  }
  async sound(name: string) {
    if (performance.now() - this.lastSound < 60) return;
    this.lastSound = performance.now();
    try {
      const context = await this.ready();
      if (!this.sounds.has(name)) this.sounds.set(name, fetch(`/sfx/${name}.wav`).then(r => {
        if (!r.ok) throw new Error('sound missing'); return r.arrayBuffer();
      }).then(b => context.decodeAudioData(b)));
      const buffer = await this.sounds.get(name)!;
      const source = context.createBufferSource(); const gain = context.createGain();
      source.buffer = buffer; gain.gain.value = .32;
      source.connect(gain); gain.connect(context.destination);
      source.onended = () => { source.disconnect(); gain.disconnect(); }; source.start();
    } catch { /* A missing effect never blocks navigation or music. */ }
  }
}

export const player = new Player();
