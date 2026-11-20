import type { Music } from './types';
import { PLAYBACK_MODES, type PlaybackMode } from './playbackMode';
import { LayeredPlayback } from './layeredAudio';
import { nativeLoopRegion, loopPosition, type LoopRegion } from './audioLoop';

export interface Playback {
  trackId: string; playing: boolean; loading: boolean; error: string;
  position: number; duration: number; volume: number; loop: boolean; mode: PlaybackMode; mixerChoices: number[];
  loopRegion: LoopRegion | null;
}

/** Uses the original sample loop boundaries; the intro is played only once. */
class Player {
  private context?: AudioContext;
  private musicGain?: GainNode;
  private source?: AudioBufferSourceNode;
  private sourceGain?: GainNode;
  private buffer?: AudioBuffer;
  private layered?: LayeredPlayback;
  private layerBuffers?: Map<string, AudioBuffer>;
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
    duration: 0, volume: .65, loop: true, mode: 'single', mixerChoices: [0,0,0,0], loopRegion: null,
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
    this.layered?.stop();this.layered=undefined;
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
    const duration = this.buffer?.duration || this.value.duration;
    return nativeLoopRegion(this.track, duration) || { start: 0, end: duration };
  }
  private position() {
    let position = this.offset + (this.context ? this.context.currentTime - this.startedAt : 0);
    const { start, end } = this.boundaries();
    if (this.value.loop && end > start) position = loopPosition(position, { start, end });
    return Math.max(0,Math.min(position, this.value.duration));
  }
  async select(track: Music, autoplay = false) {
    if (this.track?.id === track.id) { if (autoplay && !this.value.playing && !this.value.loading) await this.play(); return; }
    const generation = ++this.generation;
    this.abort?.abort(); this.stopSource();
    this.track = track; this.buffer = undefined; this.layerBuffers=undefined; this.offset = 0;
    this.update({ trackId: track.id, playing: false, loading: false, error: '', position: 0, duration: track.duration_seconds, loopRegion: nativeLoopRegion(track, track.duration_seconds) });
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
      if (track.mixer) {
        this.abort=new AbortController();
        const signal=this.abort.signal;
        const buffers=new Map<string,AudioBuffer>();
        await Promise.all([...new Set(track.mixer.streams.map(stream=>stream.path))].map(async path=>{
          const response=await fetch(encodeURI(path),{signal});
          if(!response.ok)throw new Error(`音轨读取失败（${response.status}）`);
          buffers.set(path,await context.decodeAudioData(await response.arrayBuffer()));
        }));
        if(generation!==this.generation)return;
        this.layerBuffers=buffers;
        this.update({duration:track.mixer.duration,loopRegion:nativeLoopRegion(track,track.mixer.duration),loading:false});this.start();return;
      }
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
      this.update({ duration: buffer.duration, loopRegion: nativeLoopRegion(track,buffer.duration), loading: false });
      this.start();
    } catch (error) {
      if (generation !== this.generation || (error as Error).name === 'AbortError') return;
      this.update({ loading: false, playing: false, error: (error as Error).message || '音频暂时无法播放，请重试' });
    }
  }
  private start() {
    if(this.track?.mixer && this.context && this.musicGain && this.layerBuffers) {
      this.stopSource();
      this.startedAt=this.context.currentTime+.03;
      this.layered=new LayeredPlayback(this.context,this.musicGain,this.track.mixer,this.layerBuffers,this.value.mixerChoices,this.value.loop,this.startedAt-this.offset,()=>this.finish());
      this.update({playing:true});return;
    }
    if (!this.buffer || !this.context || !this.musicGain) return;
    this.stopSource();
    const source = this.context.createBufferSource(); const gain = this.context.createGain();
    source.buffer = this.buffer; source.loop = this.value.loop;
    const { start, end } = this.boundaries(); source.loopStart = start; source.loopEnd = end;
    gain.gain.setValueAtTime(0, this.context.currentTime);
    gain.gain.linearRampToValueAtTime(1, this.context.currentTime + .06);
    source.connect(gain); gain.connect(this.musicGain);
    this.offset = Math.min(this.offset, Math.max(0, this.buffer.duration - .001));
    if (this.value.loop && end > start) this.offset = loopPosition(this.offset, { start, end });
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
    if (!this.buffer && !this.layerBuffers) { await this.loadAndPlay(this.generation); return; }
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
  setMixerChoices(choices: number[]) {
    if(choices.length!==4 || choices.some(value=>value!==0 && value!==1))return;
    this.layered?.choose(choices);this.update({mixerChoices:[...choices]});
  }
  private finish() {
    const endedId=this.value.trackId;
    this.offset=0;this.layered=undefined;
    this.update({playing:false,position:0});
    if(this.value.mode==='sequence' || this.value.mode==='shuffle')this.endedListeners.forEach(listener=>listener(endedId));
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
