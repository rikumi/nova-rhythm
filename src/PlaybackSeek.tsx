import type { CSSProperties } from 'react';
import type { Playback } from './audio';
import { player } from './audio';
import { hasLoopMarkers } from './audioLoop';
import './playbackSeek.css';

export function PlaybackSeek({ playback }: { playback: Playback }) {
  const duration = playback.duration || 1;
  const region = playback.mode === 'single' && hasLoopMarkers(playback.loopRegion, duration) ? playback.loopRegion : null;
  return <div className="playback-seek">
    <input className="seek" aria-label="播放进度" type="range" min="0" max={duration} step="0.05" value={playback.position} onChange={event => player.seek(Number(event.target.value))} style={{ '--progress': `${playback.position/duration*100}%` } as CSSProperties} />
    {region && <div className="loop-markers" aria-label={`循环片段：${region.start.toFixed(3)} 秒至 ${region.end.toFixed(3)} 秒`}>
      {(['A','B'] as const).map((label,index) => {
        const seconds = index ? region.end : region.start;
        return <span key={label} className="loop-marker" data-boundary={label} data-seconds={seconds} style={{ left: `calc(6px + (100% - 12px) * ${seconds/duration})` }} title={`${label}：${seconds.toFixed(3)} 秒`}>
          <svg viewBox="0 0 18 24" aria-hidden="true"><path d="M3 1H15Q17 1 17 3V15L9 23L1 15V3Q1 1 3 1Z"/><text x="9" y="13">{label}</text></svg>
        </span>;
      })}
    </div>}
  </div>;
}
