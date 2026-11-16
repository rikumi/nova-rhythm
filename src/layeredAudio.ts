export interface MixerCue { start: number; duration: number; offset: number }
export interface MixerStream { id: string; path: string; row?: number; option?: number; cues: MixerCue[] }
export interface MixerDefinition {
  schema_version: number; track_id: string; duration: number; loop_start: number;
  crossfade_seconds: number; streams: MixerStream[]; combinations: Record<string, number[]>;
}

/** Compact segment buffers share one AudioContext clock; muted alternatives keep time. */
export class LayeredPlayback {
  private context: AudioContext;
  private definition: MixerDefinition;
  private buffers: Map<string, AudioBuffer>;
  private gains = new Map<string, GainNode>();
  private sources = new Set<AudioBufferSourceNode>();
  private master: GainNode;
  private origin: number;
  private loop: boolean;
  private nextCycle = 0;
  private timer?: ReturnType<typeof setInterval>;
  private stopped = false;
  private onEnded: () => void;

  constructor(context: AudioContext, destination: AudioNode, definition: MixerDefinition, buffers: Map<string, AudioBuffer>, choices: number[], loop: boolean, origin: number, onEnded: () => void) {
    this.context=context;this.definition=definition;this.buffers=buffers;this.loop=loop;this.origin=origin;this.onEnded=onEnded;
    this.master=context.createGain();this.master.connect(destination);
    this.master.gain.setValueAtTime(0,context.currentTime);
    this.master.gain.linearRampToValueAtTime(1,context.currentTime+.06);
    for (const stream of definition.streams) {
      const gain=context.createGain();gain.connect(this.master);
      gain.gain.value=stream.row === undefined || choices[stream.row] === stream.option ? 1 : 0;
      this.gains.set(stream.id,gain);
    }
    this.tick();this.timer=setInterval(()=>this.tick(),250);
  }
  private tick() {
    if (this.stopped) return;
    const { duration,loop_start,streams }=this.definition;
    const period=duration-loop_start, now=this.context.currentTime;
    if (!this.loop && now>=this.origin+duration) { this.stop();this.onEnded();return; }
    // Keep multiple cycles scheduled so background timer throttling cannot cause gaps.
    const horizon=now+period*3;
    while ((this.loop || this.nextCycle===0) && this.origin+(this.nextCycle ? duration+(this.nextCycle-1)*period : 0)<=horizon) {
      const cycle=this.nextCycle++;
      for (const stream of streams) for (const cue of stream.cues) {
        if (cycle && cue.start<loop_start) continue;
        const when=this.origin+cue.start+(cycle ? cycle*period : 0);
        const skipped=Math.max(0,now-when);
        if (skipped>=cue.duration) continue;
        const buffer=this.buffers.get(stream.path)!;
        const offset=cue.offset+skipped;
        const length=Math.min(cue.duration-skipped,buffer.duration-offset);
        if (length<=0) continue;
        const source=this.context.createBufferSource();source.buffer=buffer;
        source.connect(this.gains.get(stream.id)!);this.sources.add(source);
        source.onended=()=>{this.sources.delete(source);source.disconnect();};
        source.start(Math.max(now,when),offset,length);
      }
    }
  }
  choose(choices: number[]) {
    const now=this.context.currentTime;
    for (const stream of this.definition.streams) {
      if (stream.row===undefined) continue;
      const gain=this.gains.get(stream.id)!.gain;
      if (gain.cancelAndHoldAtTime) gain.cancelAndHoldAtTime(now);
      else {const value=gain.value;gain.cancelScheduledValues(now);gain.setValueAtTime(value,now);}
      gain.linearRampToValueAtTime(choices[stream.row]===stream.option ? 1 : 0,now+this.definition.crossfade_seconds);
    }
  }
  stop() {
    if (this.stopped) return;
    this.stopped=true;clearInterval(this.timer);
    const now=this.context.currentTime;
    this.master.gain.cancelScheduledValues(now);this.master.gain.setValueAtTime(this.master.gain.value,now);
    this.master.gain.linearRampToValueAtTime(0,now+.045);
    for (const source of this.sources) { try {source.stop(now+.05);} catch {/* already stopped */} }
    setTimeout(()=>{for(const source of this.sources)source.disconnect();for(const gain of this.gains.values())gain.disconnect();this.master.disconnect();},75);
  }
}
