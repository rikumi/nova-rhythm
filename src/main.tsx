import React, { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowLeft, AudioLines, Box, Check, ChevronDown, Copy, Disc3, Download, Expand, Heart, ListMusic, LoaderCircle, Music2, Pause, Play, Repeat, Repeat1, Shuffle, Search, SkipBack, SkipForward, Smartphone, Volume2, VolumeX, X } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import type { Outfit, LibraryMusic, MusicGroup } from './types';
import { player } from './audio';
import { PHONOGRAPH_HARDWARE, PHONOGRAPH_NOTE } from './nativePhonograph';
import { deviceTilt } from './deviceTilt';
import { resolveStoryLibrary, libraryGroupLabel } from './storyLibrary';
import { adjacentLibraryTrack, libraryQueue, libraryTrackUrl } from './libraryNavigation';
import { MODE_LABELS, nextPlaybackMode, nextQueueIndex } from './playbackMode';
import { musicTitleParts } from './musicTitle';
import { ScrollingText } from './ScrollingText';
import { OutlinedName } from './OutlinedName';
import { loadOutfits } from './experimentalLayering';
import { CARD_CONTENT_SCALE, backgroundLayer, cardDepths } from './parallaxDepth';
import { loadSharpManifest } from './sharpScenes';
import { downloadArtwork } from './artworkDownload';
import { SharpCacheButton } from './SharpCacheButton';
import { applyInfinityTowerMixer } from './infinitytowerMixer';
import { musicIdFromPath, musicPage, musicPath, musicUrl, outfitMusicPage, registerMusicPages, storyMusicPage, updateMusicPageMetadata } from './musicRoutes';
import './style.css';
import './storyPlayback.css';
import './pwa.css';
import './cardLighting.css';
import './cardActions.css';
import './mobilePlayback.css';
import './canvasCard.css';
import './pwa';

const ELEMENTS = ['无', '水', '火', '风', '地', '光', '暗', '无'];
const SharpScene = lazy(() => import('./SharpScene'));
const time = (value: number) => `${Math.floor(value / 60)}:${Math.floor(value % 60).toString().padStart(2, '0')}`;
const melodyTime = (value: number) => { const seconds = Math.floor(value); return seconds >= 60 ? `${Math.floor(seconds / 60)} 分钟 ${seconds % 60} 秒` : `${seconds} 秒`; };
function readStorage<T,>(key: string, fallback: T): T { try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback; } catch { return fallback; } }
function writeStorage(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private browsing */ } }

function MusicTitle({ title, scrollingSubtitle = false }: { title: string; scrollingSubtitle?: boolean }) {
  const parts = musicTitleParts(title);
  return <><span className="music-title-line">{parts.title}</span>{parts.subtitle && (scrollingSubtitle ? <ScrollingText className="music-subtitle" text={parts.subtitle} /> : <small className="music-subtitle">{parts.subtitle}</small>)}</>;
}

function InfinityTowerMixer({ track, onPlay }: { track: LibraryMusic; onPlay: (track: LibraryMusic) => void }) {
  const playback=useSyncExternalStore(player.subscribe,player.snapshot);
  const current=playback.trackId===track.id;
  const definition=track.mixer!;
  const activeRow=definition.streams.find(stream=>stream.row!==undefined && stream.cues.some(cue=>playback.position>=cue.start && playback.position<cue.start+cue.duration))?.row;
  return <section className="infinity-mixer" data-content-id={track.id} aria-label="心危擂台段落混音">
    <button className="infinity-mixer-heading" onClick={()=>{if(current && playback.playing)void player.toggle();else onPlay(track);}} aria-label={current && playback.playing ? '暂停心危擂台混音' : '播放心危擂台混音'}>
      <strong><MusicTitle title={track.title} /></strong>{current && playback.loading ? <LoaderCircle className="spinner" size={19}/> : current && playback.playing ? <Pause size={19}/> : <Play size={19}/>}</button>
    <div className="infinity-mixer-grid">{[0,1,2,3].flatMap(row=>[0,1].map(option=><button key={`${row}-${option}`} className={`infinity-mixer-cell ${current && playback.playing && activeRow===row ? 'is-current' : ''}`} data-row={row} data-option={option} aria-label={`片段 ${row+1} · ${option===0 ? 'A' : 'B'}`} aria-pressed={playback.mixerChoices[row]===option} onClick={()=>{
      const choices=[...playback.mixerChoices];choices[row]=option;player.setMixerChoices(choices);onPlay(track);
    }}><span>片段 {row+1}</span><strong>{option===0 ? 'A' : 'B'}</strong><i aria-hidden="true"><b/><b/><b/></i></button>))}</div>
  </section>;
}

function PlaybackModeButton({ className = '' }: { className?: string }) {
  const { mode } = useSyncExternalStore(player.subscribe, player.snapshot);
  const Icon = mode === 'single' ? Repeat1 : mode === 'shuffle' ? Shuffle : mode === 'once' ? ListMusic : Repeat;
  return <button className={`icon-button loop-button ${mode !== 'once' ? 'enabled' : ''} ${className}`} aria-label={`播放模式：${MODE_LABELS[mode]}`} title={`${MODE_LABELS[mode]}，点击切换为${MODE_LABELS[nextPlaybackMode(mode)]}`} data-mode={mode} onClick={() => player.setMode(nextPlaybackMode(mode))}><Icon size={19} /></button>;
}

function RichText({ text = '' }: { text?: string }) {
  const clean = text.replace(/\\x0b|\x0b/g, '\n').replace(/##(.*?)#\d+#/g, '$1').replace(/<ruby.*?>|<\/ruby>/g, '');
  const parts = clean.split(/(<color=#[\da-fA-F]+>.*?<\/color>)/g);
  return <>{parts.map((p, i) => {
    const match = /^<color=#[\da-fA-F]+>(.*?)<\/color>$/.exec(p);
    return match ? <em key={i}>{match[1]}</em> : <React.Fragment key={i}>{p.replace(/<[^>]+>/g, '')}</React.Fragment>;
  })}</>;
}

function Modal({ title, children, close, className = '' }: { title: string; children: ReactNode; close: () => void; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className={`modal ${className}`} aria-label={title} onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === e.currentTarget) close(); }}>
    <div className="modal-sheet"><header><div><h2>{title}</h2></div><button className="icon-button close" aria-label="关闭" onClick={close}><X /></button></header>{children}</div>
  </dialog>;
}

function ArtworkActions({ outfit, onExpand, action }: { outfit: Outfit; onExpand: () => void; action?: ReactNode }) {
  return <div className="card-actions">
    {action}
    <a className="save-card" href={outfit.staticImage} download={`秘纹-${outfit.name}.png`} onClick={downloadArtwork} aria-label="保存秘纹静态图"><Download size={19} /></a>
    <button className="expand-card" onClick={onExpand} aria-label="全屏欣赏秘纹"><Expand size={19} /></button>
  </div>;
}

function SensorControl({ full = false }: { full?: boolean }) {
  const sensor = useSyncExternalStore(deviceTilt.subscribe, deviceTilt.snapshot);
  if (!sensor.mobile || !sensor.supported) return null;
  const enabled = sensor.status === 'enabled';
  return <>
    <button className="capsule-toggle" aria-label={enabled ? '关闭重力感应' : '开启重力感应'} title={enabled ? '关闭重力感应' : '开启重力感应'} aria-pressed={enabled} disabled={sensor.status === 'requesting'} onClick={() => { if (enabled) deviceTilt.disable(); else void deviceTilt.enable(); }} style={full && enabled ? { color: '#7ff6ed' } : undefined}>
      <span className="capsule-checkbox" aria-hidden="true" />{full ? <Smartphone size={21} /> : sensor.status === 'requesting' ? '授权中' : sensor.status === 'denied' ? '重试感应' : '重力感应'}
    </button>
    {sensor.error && <span role="status" style={full ? { position: 'fixed', top: 80, right: 20, maxWidth: 'calc(100vw - 40px)', fontSize: 12, padding: '8px 12px', background: '#142440e6' } : { flexBasis: '100%', textAlign: 'center', fontSize: 12 }}>{sensor.error}</span>}
  </>;
}

function SharpCard({outfit,full=false,suspended=false,onExpand,action}:{outfit:Outfit;full?:boolean;suspended?:boolean;onExpand?:()=>void;action?:ReactNode}){
  const motion=outfit.card.motion||{rotation_x:3,rotation_y:-8};
  return <div className={`live-card sharp-card ${full?'full-card':''}`} style={{'--tilt-x':`${-motion.rotation_x}deg`,'--tilt-y':`${-motion.rotation_y}deg`} as CSSProperties}>
    <div className={`card-frame rarity-${outfit.rarity}`}><div className="card-backdrop-tint" aria-hidden="true" />
      <div className="card-window"><img className="sharp-static" src={outfit.fullCover || outfit.staticImage} alt="" draggable={false} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:full?'contain':'cover',pointerEvents:'none'}}/><Suspense fallback={<div className="card-loading-toast" role="status">正在加载三维场景…</div>}><SharpScene full={full} suspended={suspended} code={outfit.code} name={outfit.name}/></Suspense></div>
      <img className="native-frame" src="/ui/rare_outfit_5.png" alt=""/>
    </div>
    {!full&&<ArtworkActions outfit={outfit} action={action} onExpand={()=>onExpand?.()}/>}
  </div>;
}

function FullscreenArtwork({ outfit, close, sharp=false, action }: { outfit: Outfit; close: () => void; sharp?:boolean; action?:ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="fullscreen-artwork" aria-label={`${outfit.name}全屏差分`} onCancel={e => { e.preventDefault(); close(); }}>
    {sharp?<SharpCard outfit={outfit} full/>:<Card outfit={outfit} full />}
    <div className="fullscreen-artwork-actions"><SensorControl full />{action}<a href={outfit.staticImage} download={`秘纹-${outfit.name}.png`} onClick={downloadArtwork} aria-label="保存秘纹静态图"><Download size={22} /></a><button aria-label="关闭全屏" onClick={close}><X size={25} /></button></div>
  </dialog>;
}

function CardLayer({ src, style, background, index, visible, onReady, onReveal, flat = false }: { src:string; style?:CSSProperties; background?:boolean; index:number; visible:boolean; onReady:(index:number)=>void; onReveal:(index:number)=>void; flat?:boolean }) {
  const ref=useRef<HTMLImageElement>(null);
  useEffect(()=>{
    const image=ref.current;if(!image)return;
    let mounted=true,reported=false;
    const ready=()=>{void image.decode().catch(()=>{}).then(()=>{if(mounted && !reported && image.naturalWidth){reported=true;onReady(index);}});};
    image.addEventListener('load',ready);
    if(image.complete && image.naturalWidth)ready();
    return ()=>{mounted=false;image.removeEventListener('load',ready);};
  },[src,index,onReady]);
  return <div className={`card-layer-stage ${visible ? 'is-loaded' : ''}`} style={{zIndex:index}} onAnimationStart={event=>{if(event.target===event.currentTarget && event.animationName==='card-layer-arrive')onReveal(index);}}><img ref={ref} className={flat ? 'flat-cover' : 'card-layer'} data-background={background} src={src} alt="" style={style} draggable={false} /></div>;
}

function Card({ outfit, full = false, onExpand, action }: { outfit: Outfit; full?: boolean; onExpand?: () => void; action?:ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const lightRef = useRef<HTMLDivElement>(null);
  const target = useRef({ x: 0, y: 0, active: false });
  const dragPointer = useRef<number | null>(null);
  const reduced = useRef(false);
  const total = outfit.card.layers.length || 1;
  const depths = useMemo(() => cardDepths(outfit.card), [outfit.card]);
  // The Unity camera faces positive Z: greater native Z is farther away.
  const revealOrder=useMemo(()=>outfit.card.layers.length
    ? outfit.card.layers.map((layer,index)=>({index,z:layer.native_z ?? 0})).sort((a,b)=>b.z-a.z || a.index-b.index).map(layer=>layer.index)
    : [0],[outfit]);
  const [readyLayers,setReadyLayers]=useState<Set<number>>(()=>new Set());
  const [visibleLayers,setVisibleLayers]=useState(0);
  const [firstReveal,setFirstReveal]=useState<number|null>(null);
  const layerReady=useCallback((index:number)=>setReadyLayers(previous=>new Set(previous).add(index)),[]);
  // Anchor every arrival to the first paint, keeping the entire stagger within 200 ms.
  const layerRevealed=(index:number)=>{if(index===revealOrder[0])setFirstReveal(performance.now());};
  useEffect(()=>{
    const next=revealOrder[visibleLayers];
    if(next===undefined || !readyLayers.has(next) || (visibleLayers>0 && firstReveal===null))return;
    const timer=window.setTimeout(()=>{
      setVisibleLayers(count=>count+1);
    },Math.max(0,(firstReveal ?? performance.now())+visibleLayers*200/Math.max(1,total-1)-performance.now()));
    return ()=>window.clearTimeout(timer);
  },[readyLayers,visibleLayers,firstReveal,revealOrder,total]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updatePreference = () => { reduced.current = preference.matches; };
    updatePreference(); preference.addEventListener('change', updatePreference);
    let frame = 0; let x = 0; let y = 0;
    let lastX: string | undefined; let lastY: string | undefined;
    let previous = performance.now();
    const tick = (now: number) => {
      const sensor = deviceTilt.read(now);
      const input = target.current.active ? target.current : sensor.active ? sensor : target.current;
      const smoothing = 1-Math.exp(-Math.min(now-previous, 100)/240); previous = now;
      x += (input.x - x) * smoothing;
      y += (input.y - y) * smoothing;
      const nextX = String(Math.round((reduced.current ? 0 : x) * 1000) / 1000);
      const nextY = String(Math.round((reduced.current ? 0 : y) * 1000) / 1000);
      const style = ref.current?.style;
      if (style && nextX !== lastX) { style.setProperty('--mx', nextX); lastX = nextX; }
      if (style && nextY !== lastY) { style.setProperty('--my', nextY); lastY = nextY; }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick); return () => { cancelAnimationFrame(frame); preference.removeEventListener('change', updatePreference); };
  }, []);
  useEffect(() => {
    const element=ref.current;
    const blockScroll=(event:TouchEvent)=>{if(event.cancelable)event.preventDefault();};
    element?.addEventListener('touchmove',blockScroll,{passive:false});
    return ()=>element?.removeEventListener('touchmove',blockScroll);
  },[]);
  const move = (e: React.PointerEvent) => {
    if (e.pointerType !== 'mouse' && dragPointer.current !== e.pointerId) return;
    const box = e.currentTarget.getBoundingClientRect();
    target.current = { x: Math.max(-1, Math.min(1, (e.clientX - box.left) / box.width * 2 - 1)), y: Math.max(-1, Math.min(1, (e.clientY - box.top) / box.height * 2 - 1)), active: true };
    const light = lightRef.current;
    if (light) {
      const bounds = light.getBoundingClientRect();
      const inside = e.clientX >= bounds.left && e.clientX <= bounds.right && e.clientY >= bounds.top && e.clientY <= bounds.bottom;
      const values = { '--light-x': `${Math.round((e.clientX - bounds.left) / bounds.width * 1000) / 10}%`, '--light-y': `${Math.round((e.clientY - bounds.top) / bounds.height * 1000) / 10}%`, '--light-active': inside ? '1' : '0' };
      for (const [name, value] of Object.entries(values)) if (light.style.getPropertyValue(name) !== value) light.style.setProperty(name, value);
    }
  };
  const hideLight = () => { lightRef.current?.style.setProperty('--light-active', '0'); };
  const beginDrag=(e:React.PointerEvent<HTMLDivElement>)=>{
    if(e.pointerType==='mouse' || !e.isPrimary || (e.target instanceof Element && e.target.closest('button,a')))return;
    dragPointer.current=e.pointerId;e.currentTarget.setPointerCapture(e.pointerId);move(e);
  };
  const endDrag=(e:React.PointerEvent<HTMLDivElement>)=>{
    if(dragPointer.current!==e.pointerId)return;
    dragPointer.current=null;target.current={x:0,y:0,active:false};
    hideLight();
    if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
  };
  const base = outfit.card.mask_size || 712;
  const motion = outfit.card.motion || { rotation_x: 3, rotation_y: -8 };
  const aspect = outfit.card.layers.length ? outfit.card.layers[0].width / outfit.card.layers[0].height : 1;
  const sinX = Math.sin(motion.rotation_x * Math.PI / 180), sinY = Math.sin(motion.rotation_y * Math.PI / 180);
  const maxDepth = Math.max(0, ...depths.map(Math.abs));
  const canvasScale = Math.max(1.06, 1 + 2 * maxDepth * Math.abs(sinX) + .04, (1 + 2 * maxDepth * Math.abs(sinY) + .04) / aspect);
  const canvasUnit = `min(100dvh, ${100/aspect}dvw)`;
  return <div ref={ref} className={`live-card ${full ? 'full-card' : ''} ${outfit.card.layout === 'canvas' ? 'canvas-card' : ''}`} style={{ '--tilt-x': `${-motion.rotation_x}deg`, '--tilt-y': `${-motion.rotation_y}deg` } as CSSProperties} onPointerDown={beginDrag} onPointerMove={move} onPointerUp={endDrag} onPointerCancel={endDrag} onLostPointerCapture={endDrag} onPointerLeave={() => { if(dragPointer.current===null)target.current = { x: 0, y: 0, active: false }; hideLight(); }}>
    <div className={`card-frame rarity-${outfit.rarity}`}>
      <div className="card-backdrop-tint" aria-hidden="true" />
      <div className="card-glint" />
      <div className="card-window" data-content-scale={CARD_CONTENT_SCALE} data-depth-span={(depths.length ? Math.max(...depths)-Math.min(...depths) : 0).toFixed(6)}>
        {outfit.card.layers.length ? revealOrder.map(i => {
          const layer = outfit.card.layers[i];
          const background = backgroundLayer(layer, i);
          const fit = background ? 1 : CARD_CONTENT_SCALE;
          const projectedZ = depths[i] * base / fit;
          const style = outfit.card.layout === 'canvas' ? {
            left: full ? `calc(50% + var(--mx) * ${depths[i]*sinY} * ${canvasUnit})` : `calc(50% + var(--mx) * ${depths[i]*sinY*100}%)`,
            top: full ? `calc(50% - var(--my) * ${depths[i]*sinX} * ${canvasUnit})` : `calc(50% - var(--my) * ${depths[i]*sinX*100}%)`,
            width: full ? `calc(${aspect*canvasScale} * ${canvasUnit})` : 'auto',
            height: full ? `calc(${canvasScale} * ${canvasUnit})` : `${canvasScale*100}%`,
            transform: 'translate(-50%, -50%)',
            '--layer-opacity': layer.opacity,
          } as CSSProperties : {
            left: full ? `calc(50% + ${layer.x / base * 100 * fit}dvh)` : `${50 + layer.x / base * 100 * fit}%`,
            top: full ? `calc(50% - ${layer.y / base * 100 * fit}dvh)` : `${50 - layer.y / base * 100 * fit}%`,
            width: `${layer.width / base * 100 * fit}${full ? 'dvh' : '%'}`, height: `${layer.height / base * 100 * fit}${full ? 'dvh' : '%'}`,
            '--px': `${-layer.pivot.x * 100}%`, '--py': `${-(1 - layer.pivot.y) * 100}%`,
            '--shift-x': `${projectedZ * Math.sin(motion.rotation_y * Math.PI / 180) / layer.width * 100}%`,
            '--shift-y': `${-projectedZ * Math.sin(motion.rotation_x * Math.PI / 180) / layer.height * 100}%`,
            '--rz': `${-layer.rotation}deg`, '--layer-opacity':layer.opacity,
          } as CSSProperties;
          return <CardLayer key={`${layer.path}-${i}`} src={layer.path} style={style} background={background} index={i} visible={revealOrder.indexOf(i)<visibleLayers} onReady={layerReady} onReveal={layerRevealed} />;
        }) : <CardLayer src={outfit.fullCover || outfit.cover} index={0} visible={visibleLayers>0} onReady={layerReady} onReveal={layerRevealed} flat />}
        {/* {!outfit.card.layers.some(l => l.is_title) && <div className="card-title-art"><b>{outfit.name}</b></div>} */}
        <div ref={lightRef} className="card-light" style={{zIndex:total+1}} />
        {readyLayers.size<total && <div className="card-loading-toast" style={{zIndex:total+2}} role="status" aria-live="polite"><LoaderCircle className="spinner" size={16}/>正在加载图层 {readyLayers.size}/{total}…</div>}
      </div>
      <img className="native-frame" src="/ui/rare_outfit_5.png" alt="" />
    </div>
    {!full && <ArtworkActions outfit={outfit} action={action} onExpand={() => onExpand?.()} />}
  </div>;
}

function Phonograph({ outfit, playing, onExpand, action }: { outfit: Outfit; playing: boolean; onExpand: () => void; action?:ReactNode }) {
  return <div className={`phonograph-view ${playing ? 'is-playing' : ''}`} aria-label="秘纹唱机">
    <div className="turntable">
      <img className="turntable-base" src="/ui/db_outfit_bg.png" alt="" />
      <div className="record-orbit">
        <div className="record-disc" style={{ animationPlayState: playing ? 'running' : 'paused' }}>
          <img className="record-label" src={outfit.fullCover || outfit.staticImage} alt={`${outfit.name}封面`} draggable />
          <img className="record-grooves" src="/ui/zs_outfit_record.png" alt="" />
        </div>
        <div className="record-reflection" />
      </div>
      <div className="phonograph-hardware" aria-hidden="true">{PHONOGRAPH_HARDWARE.map(sprite => <img key={sprite.name} className={`hardware-${sprite.name}`} src={sprite.src} alt="" style={{
        left: `${(526 + sprite.x) / 1052 * 100}%`, top: `${(355 - sprite.y) / 710 * 100}%`,
        width: `${sprite.width / 1052 * 100}%`, height: `${sprite.height / 710 * 100}%`,
        transformOrigin: `${sprite.pivot.x * 100}% ${(1 - sprite.pivot.y) * 100}%`,
        transform: `translate(${-sprite.pivot.x * 100}%, ${-(1 - sprite.pivot.y) * 100}%) rotate(${-sprite.rotation}deg) scaleX(${sprite.flip_x})`,
        opacity: sprite.opacity,
      }} />)}</div>
      <div className="phonograph-effects" aria-hidden="true">
        <div className="record-rings"><img className="record-pulse" src="/ui/Disc_Bg_03.png" alt="" style={{ '--delay': '0s' } as CSSProperties} /></div>
        <div className="record-particles">{Array.from({ length: 16 }, (_, i) => {
          const angle = i * 2.39996;
          return <i className="record-particle" key={i} style={{ '--ox': `${Math.cos(angle) * 28}%`, '--oy': `${Math.sin(angle) * 38}%`, '--dx': `${Math.cos(angle) * (65 + i % 4 * 18)}px`, '--dy': `${Math.sin(angle) * (65 + i % 3 * 18)}px`, '--duration': `${2 + i % 5}s`, '--delay': `${-i * .47}s`, '--size': `${2 + i % 3}px` } as CSSProperties} />;
        })}</div>
        <div className="record-notes">{Array.from({ length: 3 }, (_, i) => <span className="record-note" key={i} style={{ '--delay': `${-i}s`, '--drift': `${-25 + i * 23}px`, '--tilt': `${-18 + i * 15}deg`, '--note-width': `${(PHONOGRAPH_NOTE.min_size + i * (PHONOGRAPH_NOTE.max_size - PHONOGRAPH_NOTE.min_size) / 2) * PHONOGRAPH_NOTE.ui_scale / 1052 * 100}%` } as CSSProperties}><i className="game-note-sprite" style={{ backgroundPosition: i % 2 ? '100% 0' : '0 0' }} /></span>)}</div>
      </div>
    </div>
    <ArtworkActions outfit={outfit} action={action} onExpand={onExpand} />
  </div>;
}

function ArchiveApp({ active, onBack, fromStory = false }: { active: boolean; onBack: () => void; fromStory?: boolean }) {
  const [items, setItems] = useState<Outfit[]>([]);
  const [loadError, setLoadError] = useState('');
  const [selectedId, setSelectedId] = useState<number>(() => {
    const url = new URLSearchParams(location.search).get('disc');
    return url ? Number(url) : musicPage()?.outfitId || readStorage('nova-selected', 214055);
  });
  const [melody, setMelody] = useState(()=>musicPage()?.melodyIndex || 0);
  const [showCollection, setShowCollection] = useState(false);
  const [showStory, setShowStory] = useState(false);
  const [full, setFull] = useState(false);
  const [sharpCode,setSharpCode]=useState<string|null>(null);
  const [sharpSizes,setSharpSizes]=useState<Record<string,number>>({});
  const [artworkMode, setArtworkMode] = useState<'difference' | 'phonograph'>(() => readStorage<string>('nova-artwork-mode', 'difference') === 'phonograph' ? 'phonograph' : 'difference');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [favorites, setFavorites] = useState<number[]>(() => readStorage('nova-favorites', []));
  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => readStorage('nova-sfx', true));
  const [showVolume, setShowVolume] = useState(false);
  const [toast, setToast] = useState('');
  const playback = useSyncExternalStore(player.subscribe, player.snapshot);
  const chosen = items.find(o => o.id === selectedId) || items[0];
  const sharpAvailable=!!chosen&&Object.hasOwn(sharpSizes,chosen.code);
  const useSharp=sharpAvailable&&sharpCode===chosen.code;
  useEffect(()=>{setSharpCode(null);},[chosen?.code,active]);
  const selectedIndex = chosen ? items.indexOf(chosen) : 0;
  const currentMusic = chosen?.music[melody] || chosen?.music[0];
  const favorite = chosen && favorites.includes(chosen.id);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { Promise.all([loadOutfits(location.href),loadSharpManifest().catch(()=>({outfits:{}}))]).then(([data,manifest]) => {
    setSharpSizes(Object.fromEntries(Object.entries(manifest.outfits).map(([code,info])=>[code,info.compressed_bytes||0])));
    registerMusicPages(data.items.flatMap(outfit=>outfit.music.map((music,index)=>outfitMusicPage(outfit,music,index))));
    const requested=musicIdFromPath(location.pathname);
    const outfit=data.items.find(outfit=>outfit.music.some(music=>music.id===requested));
    if(outfit){setSelectedId(outfit.id);setMelody(outfit.music.findIndex(music=>music.id===requested));}
    setItems(data.items);
  }).catch(e => setLoadError(e.message)); }, []);
  useEffect(() => { if (active && currentMusic) void player.select(currentMusic); }, [active, currentMusic?.id]);
  useEffect(() => { if (active && chosen && currentMusic) {
    writeStorage('nova-selected',chosen.id);history.replaceState(history.state,'',musicUrl(location.href,currentMusic.id));
    updateMusicPageMetadata(outfitMusicPage(chosen,currentMusic,melody));
  } }, [active, chosen?.id, currentMusic?.id]);
  useEffect(() => { writeStorage('nova-favorites', favorites); }, [favorites]);
  useEffect(() => { writeStorage('nova-sfx', soundEnabled); }, [soundEnabled]);
  useEffect(() => { writeStorage('nova-artwork-mode', artworkMode); }, [artworkMode]);
  const sensorViewing = active && (full || artworkMode === 'difference' && !showCollection && !showStory);
  useEffect(() => { deviceTilt.setViewing(sensorViewing); return () => deviceTilt.setViewing(false); }, [sensorViewing]);
  const sound = (name: string) => { if (soundEnabled) void player.sound(name); };
  const notify = (message: string) => { setToast(message); if (timer.current) clearTimeout(timer.current); timer.current = setTimeout(() => setToast(''), 2400); };
  const sharpLabel=`3D${sharpAvailable&&sharpSizes[chosen.code]>0?` (${(sharpSizes[chosen.code]/1000000).toFixed(1)}MB)`:''}`;
  const artwork3DAction=sharpAvailable?<span className="model-actions"><button className="save-card three-d-card" aria-label={sharpLabel} aria-pressed={useSharp} onClick={()=>{sound('ui_outfit_button_tap');setSharpCode(useSharp?null:chosen.code);setArtworkMode('difference');}}><Box size={17}/><span>{sharpLabel}</span></button><SharpCacheButton code={chosen.code} onError={notify}/></span>:undefined;
  const copyPageLink=async()=>{
    if(!chosen || !currentMusic)return;
    const url=musicUrl(location.href,currentMusic.id);
    try {
      if(!navigator.clipboard?.writeText)throw new Error('Clipboard API unavailable');
      await navigator.clipboard.writeText(url.href);
    } catch {
      const input=document.createElement('textarea');input.value=url.href;input.readOnly=true;
      input.style.cssText='position:fixed;left:-9999px;top:0';
      const previous=document.activeElement;
      document.body.append(input);input.select();
      let copied=false;try{copied=document.execCommand('copy');}catch{/* denied */}
      input.remove();if(previous instanceof HTMLElement)previous.focus({preventScroll:true});
      if(!copied){notify('复制失败，请重试');return;}
    }
    notify('已复制链接');
  };
  const select = (outfit: Outfit, autoplay = playback.playing) => {
    if (chosen?.id === outfit.id) { setShowCollection(false); if(autoplay && currentMusic)void player.select(currentMusic,true); return; }
    sound('ui_outfit_select'); setSelectedId(outfit.id); setMelody(0); setShowCollection(false);
    if (outfit.music[0]) void player.select(outfit.music[0], autoplay);
  };
  const skip = (direction: -1 | 1) => { if (items.length) select(items[nextQueueIndex(items.length, selectedIndex, direction, playback.mode)],true); };
  useEffect(() => player.subscribeEnded(trackId => {
    if (!active || currentMusic?.id !== trackId || !items.length) return;
    const next = items[nextQueueIndex(items.length, selectedIndex, 1, player.snapshot().mode)];
    setSelectedId(next.id); setMelody(0);
    if (next.music[0]) void player.select(next.music[0], true);
  }));
  const chooseMelody = (index: number) => { if (!chosen?.music[index]) return; sound('ui_outfit_menu_select'); setMelody(index); void player.select(chosen.music[index], true); };
  const toggle = () => { sound('ui_outfit_slide'); void player.toggle(); };
  const toggleFavorite = () => { if (!chosen) return; sound('ui_common_confirm'); setFavorites(f => f.includes(chosen.id) ? f.filter(id => id !== chosen.id) : [...f, chosen.id]); notify(favorite ? '已移出珍藏' : '已加入珍藏'); };
  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if (!active || e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || showCollection || showStory || full) return;
      if (e.code === 'Space') { e.preventDefault(); toggle(); }
      if (e.code === 'ArrowLeft') { e.preventDefault(); skip(-1); }
      if (e.code === 'ArrowRight') { e.preventDefault(); skip(1); }
    };
    window.addEventListener('keydown', handle); return () => window.removeEventListener('keydown', handle);
  });

  if (!chosen) return <div className="loading-screen"><img src="/ui/zs_outfit_level.png" alt="" /><h1>星塔秘纹</h1>{loadError ? <><p>{loadError}</p><button onClick={() => location.reload()}>重新加载</button></> : <><LoaderCircle className="spinner" /><p>正在打开音乐档案…</p></>}</div>;
  const filtered = items.filter(item => {
    const search = `${item.name} ${item.characters.join(' ')} ${item.tags.join(' ')}`.toLowerCase();
    return search.includes(query.toLowerCase()) && (filter === 'all' || filter === 'favorites' && favorites.includes(item.id) || String(item.element) === filter);
  });
  const playbackTitle = musicTitleParts(currentMusic?.display_title || chosen.name);
  const playbackSubtitle = currentMusic?.display_subtitle || playbackTitle.subtitle || (chosen.activity?.id && chosen.activity.name?.trim() ? chosen.activity.name : '星塔唱片');
  return <div className="app archive-only">
    <div className="room-background" aria-hidden="true" /><div className="room-haze" aria-hidden="true" />
    <div className="dust-field" aria-hidden="true">{Array.from({ length: 14 }, (_, i) => <i key={i} style={{ '--n': i } as CSSProperties} />)}</div>
    <header className="topbar">
      <div className="topbar-brand"><button className="back-button" aria-label={fromStory ? '返回故事旋律' : '返回主页面'} onClick={() => { sound('ui_common_back'); onBack(); }}><ArrowLeft /></button><div className="title-ribbon"><img src="/ui/zs_top_title.png" alt="" /><h1>秘纹</h1></div></div>
      <div className="topbar-actions"><span className="collection-counter"><Disc3 size={17} />{String(selectedIndex + 1).padStart(3, '0')}<small>/ {items.length}</small></span><button className="collection-button copy-link-button" aria-label="复制当前秘纹链接" title="复制链接" onClick={() => void copyPageLink()}><Copy size={19} /></button><button className="collection-button" onClick={() => { sound('ui_common_menu'); setShowCollection(true); }}><ListMusic size={19} />秘纹一览<ChevronDown size={14} /></button></div>
    </header>

    <main className="main-stage">
      <div className="archive-scene scene-enter" key={chosen.id}>
        <section className={`archive-artwork mode-${artworkMode}`} aria-label={`${chosen.name}专辑展示`}>
          <div className="artwork-mode-switch" role="group" aria-label="专辑展示模式" style={{ flexWrap: 'wrap' }}>
            <button aria-pressed={artworkMode === 'difference'&&!useSharp} onClick={() => { sound('ui_outfit_button_tap'); setSharpCode(null);setArtworkMode('difference'); }}><Expand size={16} />差分</button>
            <button aria-pressed={artworkMode === 'phonograph'} onClick={() => { sound('ui_outfit_button_tap'); setSharpCode(null);setArtworkMode('phonograph'); }}><Disc3 size={17} />唱机</button>
            {artworkMode === 'difference' && <SensorControl />}
          </div>
          <div className="archive-cover-wrap"><div className="card-aura" />{artworkMode === 'difference' ? (useSharp ? <SharpCard outfit={chosen} action={artwork3DAction} suspended={full || !active} onExpand={() => { sound('ui_common_click_select'); setFull(true); }}/> : <Card key={`${chosen.id}-${active}`} outfit={chosen} action={artwork3DAction} onExpand={() => { sound('ui_common_click_select'); setFull(true); }} />) : <Phonograph outfit={chosen} action={artwork3DAction} playing={playback.playing} onExpand={() => { sound('ui_common_click_select'); setFull(true); }} />}</div>
        </section>
        <aside className="archive-panel">
          <section className="native-archive-sheet" aria-label="秘纹档案">
            <header className="native-archive-name"><img src="/ui/zs_outfit_title_1.png" alt="" /><h3 aria-label={chosen.storyTitle || chosen.name}><OutlinedName text={chosen.storyTitle || chosen.name} /></h3><button className={`icon-button ${favorite ? 'is-favorite' : ''}`} onClick={toggleFavorite} aria-label={favorite ? '取消珍藏' : '珍藏秘纹'}><Heart size={20} fill={favorite ? 'currentColor' : 'none'} /></button></header>
            <section className="recorded-quote" aria-label="收录语"><h4>收录语</h4><div className="quote-copy"><RichText text={chosen.literary || chosen.description} /></div></section>
            <button className="native-story-entry" onClick={() => { sound('ui_outfit_button_tap'); setShowStory(true); }}><img className="native-story-decoration decoration-left" src="/ui/db_stage_story3.png" alt="" /><img className="native-story-decoration decoration-right" src="/ui/zs_stage_point.png" alt="" /><i className="native-story-icon" aria-hidden="true" /><span>秘纹故事</span><i className="native-story-arrow" aria-hidden="true" /></button>
            <div className="archive-tracks">{chosen.music.map((music, i) => <button className={`archive-track ${melody === i ? 'selected' : ''} ${melody === i && playback.playing ? 'is-playing' : ''}`} key={music.id} onClick={() => chooseMelody(i)} aria-pressed={melody === i}><div><b><span className="native-melody-bars" aria-hidden="true"><i /><i /><i /></span>{music.title}</b><small><i className="native-melody-time-icon" aria-hidden="true" />{melodyTime(music.duration_seconds)}</small></div></button>)}</div>
          </section>
        </aside>
      </div>
    </main>

    <section className="transport" aria-label="音乐播放控制">
      <button className="transport-cover" onClick={() => setFull(true)} aria-label="全屏欣赏秘纹"><img src={chosen.thumbnail} alt="" /><span><Music2 size={16} /></span></button>
      <div className="transport-meta"><strong><span className="music-title-line">{playbackTitle.title}</span></strong><ScrollingText text={playbackSubtitle} /></div>
      <div className="transport-buttons"><button className="icon-button" onClick={() => skip(-1)} aria-label="上一枚秘纹"><SkipBack size={19} fill="currentColor" /></button><button className="play-button" onClick={toggle} aria-label={playback.playing ? '暂停播放' : '播放音乐'} disabled={playback.loading}>{playback.loading ? <LoaderCircle className="spinner" /> : playback.playing ? <Pause size={23} fill="currentColor" /> : <Play size={23} fill="currentColor" />}</button><button className="icon-button" onClick={() => skip(1)} aria-label="下一枚秘纹"><SkipForward size={19} fill="currentColor" /></button></div>
      <div className="progress-control"><div className="progress-label"><span>{time(playback.position)}</span><span>{time(playback.duration)}</span></div><input className="seek" aria-label="播放进度" type="range" min="0" max={playback.duration || 1} step="0.05" value={playback.position} onChange={e => player.seek(Number(e.target.value))} style={{ '--progress': `${playback.position / (playback.duration || 1) * 100}%` } as CSSProperties} /></div>
      <div className="transport-options"><PlaybackModeButton /><div className="volume-wrap"><button className="icon-button" aria-label="音量设置" aria-expanded={showVolume} onClick={() => setShowVolume(!showVolume)}>{playback.volume ? <Volume2 size={20} /> : <VolumeX size={20} />}</button>{showVolume && <div className="volume-popup"><input aria-label="音乐音量" type="range" min="0" max="1" step="0.01" value={playback.volume} onChange={e => player.setVolume(Number(e.target.value))} /><span>{Math.round(playback.volume * 100)}%</span><button className={soundEnabled ? 'enabled' : ''} aria-pressed={soundEnabled} onClick={() => setSoundEnabled(!soundEnabled)}>交互音效 {soundEnabled ? '开' : '关'}</button></div>}</div></div>
    </section>
    {playback.error && <div className="audio-error" role="alert">{playback.error}<button onClick={() => void player.play()}>重试</button></div>}


    {toast && <div className="toast" role="status"><Check size={16} />{toast}</div>}

    {showCollection && <Modal title="秘纹一览" close={() => { sound('ui_common_back'); setShowCollection(false); }} className="collection-modal"><div className="collection-tools"><label className="search-box"><Search size={18} /><input autoFocus value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索秘纹、旅人或标签" aria-label="搜索秘纹" />{query && <button aria-label="清除搜索" onClick={() => setQuery('')}><X size={14} /></button>}</label><span>{filtered.length} / {items.length}</span></div><div className="collection-filters"><button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>全部</button><button className={filter === 'favorites' ? 'active' : ''} onClick={() => setFilter('favorites')}><Heart size={13} />珍藏</button>{[1, 2, 3, 4, 5, 6, 7].map(element => <button className={filter === String(element) ? 'active' : ''} key={element} onClick={() => setFilter(String(element))}>{ELEMENTS[element]}</button>)}</div><div className="collection-grid">{filtered.map((item, i) => <React.Fragment key={item.id}>{(i === 0 || filtered[i - 1].activity.id !== item.activity.id || filtered[i - 1].activity.date !== item.activity.date) && <div className="collection-activity"><span>{item.activity.name}</span><small>{item.activity.date ? item.activity.date.slice(0, 10).replaceAll("-", ".") : "常驻"}</small></div>}<button className={`collection-item ${chosen.id === item.id ? 'selected' : ''}`} onClick={() => select(item)}><div className={`collection-image rarity-${item.rarity}`}><img src={item.thumbnail} alt="" loading="lazy" /><span className="collection-stars">{'★'.repeat(item.rarity)}</span>{favorites.includes(item.id) && <Heart className="collection-heart" size={13} fill="currentColor" />}{chosen.id === item.id && <span className="selected-check"><Check size={16} /></span>}</div><strong>{item.name}</strong><small>出镜旅人：{item.characters.filter(Boolean).join(' / ') || '未知'}</small></button></React.Fragment>)}{!filtered.length && <div className="empty-collection"><Search size={28} /><p>{filter === 'favorites' ? '还没有找到珍藏的秘纹' : '没有找到这枚秘纹'}</p><button onClick={() => { setQuery(''); setFilter('all'); }}>查看全部秘纹</button></div>}</div></Modal>}
    {showStory && <Modal title={chosen.storyTitle || chosen.name} close={() => setShowStory(false)} className="story-modal"><article className="full-story"><RichText text={chosen.story || chosen.literary} /></article><div className="story-ending">✦</div></Modal>}
    {full && <FullscreenArtwork outfit={chosen} action={artwork3DAction} sharp={useSharp} close={() => setFull(false)} />}
  </div>;
}

const SECTIONS = [
  { id: 'outfit', name: '秘纹旋律', icon: '/ui/home-btn_main_system_outfit_L.png' },
  { id: 'library', name: '故事旋律', icon: '/ui/home-native-story.svg' },
] as const;
type Page = 'home' | typeof SECTIONS[number]['id'];
function readPage(): Page {
  const id=musicIdFromPath(location.pathname);
  if(id)return musicPage(id)?.kind || 'library';
  const hash = location.hash.replace(/^#\/?/, '');
  if (['combat', 'story', 'system'].includes(hash)) return 'library';
  return SECTIONS.some(s => s.id === hash) ? hash as Page : hash === 'home' ? 'home' : new URLSearchParams(location.search).has('track') ? 'library' : new URLSearchParams(location.search).has('disc') ? 'outfit' : 'home';
}
function MusicLibrary({ active, onBack, onOpenOutfit }: { active: boolean; onBack: () => void; onOpenOutfit: (id: number) => void }) {
  const [tracks, setTracks] = useState<LibraryMusic[]>([]);
  const [groups, setGroups] = useState<MusicGroup[]>([]);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const pendingGroupHeader = useRef<string | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const playback = useSyncExternalStore(player.subscribe, player.snapshot);
  const [selected, setSelected] = useState<LibraryMusic>();
  const [routeVersion, setRouteVersion] = useState(0);
  const section = SECTIONS.find(s => s.id === 'library')!;
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch('/data/story-melodies.json', { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('故事旋律映射读取失败'); return r.json(); }),
      fetch('/data/library.json', { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('音乐读取失败'); return r.json(); }),
      fetch('/data/infinitytower-mixer.json', { signal: controller.signal }).then(r => r.ok ? r.json() : null).catch(()=>null),
    ]).then(([mapping, metadata, mixer]) => {
      const original=resolveStoryLibrary(mapping,metadata);const names=new Map(original.groups.map(group=>[group.id,group.name]));
      registerMusicPages(original.tracks.map(track=>storyMusicPage(track,names.get(track.group_id)||'星塔唱片')));
      const d=applyInfinityTowerMixer(original,mixer);setTracks(d.tracks);setGroups(d.groups);
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const change = () => setRouteVersion(version => version+1);
    window.addEventListener('popstate', change); window.addEventListener('hashchange', change);
    return () => { window.removeEventListener('popstate', change); window.removeEventListener('hashchange', change); };
  }, []);
  useEffect(() => {
    if (!active || !tracks.length) return;
    const requested = musicIdFromPath(location.pathname) || new URLSearchParams(location.search).get('track');
    if (!requested) return;
    const track = tracks.find(track => track.id === requested || track.legacy_ids?.includes(requested));
    if (!track) { setError('这首音乐已移除或链接无效'); return; }
    const mix=new URLSearchParams(location.search).get('mix');
    const choices=track.mixer && (mix && /^[01]{4}$/.test(mix) ? [...mix].map(Number) : track.mixer.combinations[requested]);
    if(choices)player.setMixerChoices(choices);
    const pageId=track.mixer && choices ? Object.entries(track.mixer.combinations).find(([,value])=>value.join('')===choices.join(''))?.[0] || track.id : track.id;
    if (location.pathname!==musicPath(pageId) || location.search.includes('track=') || mix || location.hash) {
      const url=libraryTrackUrl(location.href,pageId);
      history.replaceState(history.state,'',url);
    }
    const page=musicPage(pageId);if(page)updateMusicPageMetadata(page);
    setError(''); setSelected(track); setOpenGroup(track.group_id); setQuery('');
    if (player.snapshot().trackId !== track.id) void player.selectFromLink(track).catch(() => setError('音乐暂时无法播放，请点击播放重试'));
  }, [active, tracks, routeVersion]);
  useEffect(() => {
    if(!active || !openGroup || pendingGroupHeader.current!==openGroup)return;
    const frame=requestAnimationFrame(()=>{
      document.getElementById(`group-${encodeURIComponent(openGroup)}`)?.previousElementSibling?.scrollIntoView({
        block:'nearest',inline:'nearest',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      });
      pendingGroupHeader.current=null;
    });
    return ()=>cancelAnimationFrame(frame);
  },[active,openGroup]);
  useEffect(() => {
    if (!active || !selected || openGroup !== selected.group_id || pendingGroupHeader.current===openGroup) return;
    const frame = requestAnimationFrame(() => {
      document.querySelector(`[data-content-id="${CSS.escape(selected.id)}"]`)?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(frame);
  }, [active, selected?.id, openGroup]);
  const queue = libraryQueue(groups, tracks);
  const playTrack = (track: LibraryMusic) => {
    setSelected(track); setOpenGroup(track.group_id); setQuery(''); setError('');
    const id=track.mixer ? Object.entries(track.mixer.combinations).find(([,choices])=>choices.join('')===player.snapshot().mixerChoices.join(''))?.[0] || track.id : track.id;
    const url = libraryTrackUrl(location.href,id);
    const page=musicPage(id);if(page)updateMusicPageMetadata(page);
    if (url.href !== location.href) history.pushState(history.state, '', url);
    setRouteVersion(version => version+1);
    void player.select(track, true);
  };
  const skip = (direction: -1 | 1) => {
    const track = playback.mode === 'shuffle'
      ? queue[nextQueueIndex(queue.length, queue.findIndex(track => track.id === selected?.id), direction, playback.mode)]
      : adjacentLibraryTrack(queue, selected?.id || '', direction);
    if (track) playTrack(track);
  };
  useEffect(() => player.subscribeEnded(trackId => {
    if (!active || selected?.id !== trackId) return;
    const track = queue[nextQueueIndex(queue.length, queue.findIndex(track => track.id === trackId), 1, player.snapshot().mode)];
    if (track) playTrack(track);
  }));
  const search = query.trim().toLowerCase();
  const visibleGroups = groups.map(group => ({ ...group, outfit_references: (group.outfit_references || []).filter(r => !search || `${group.name} ${group.description || ''} ${r.name}`.toLowerCase().includes(search)), tracks: tracks.filter(t => t.group_id === group.id && (!search || `${group.name} ${group.description || ''} ${t.title} ${t.description || ''} ${t.source_title} ${t.uses.join(' ')}`.toLowerCase().includes(search))) })).filter(g => g.tracks.length || g.outfit_references.length);
  useEffect(() => {
    if (search) setOpenGroup(visibleGroups[0]?.id || null);
  }, [search, groups, tracks]);
  return <div className="app library-page"><div className="room-background" /><div className="room-haze" />
    <header className="topbar"><div className="topbar-brand"><button className="back-button" aria-label="返回主页面" onClick={onBack}><ArrowLeft /></button><div className="title-ribbon"><img src="/ui/zs_top_title.png" alt="" /><h1>{section.name}</h1></div></div></header>
    <main className="library-content scene-enter"><label className="search-box"><Search size={18} /><input aria-label="搜索音乐" placeholder="搜索音乐" value={query} onChange={e => setQuery(e.target.value)} /></label>
      {error && <p role="alert">{error}</p>}
      <div className="library-groups">{visibleGroups.map(group => <section className={`library-group ${openGroup === group.id ? 'is-open' : ''}`} key={group.id} data-date={group.date}>
        <button className="library-group-toggle" aria-expanded={openGroup === group.id} aria-controls={`group-${encodeURIComponent(group.id)}`} onClick={() => { if (readStorage('nova-sfx', true)) void player.sound('ui_common_menu'); pendingGroupHeader.current=openGroup===group.id ? null : group.id; setOpenGroup(current => current === group.id ? null : group.id); }}><span className="library-group-heading">{libraryGroupLabel(group.id, group.description) && <span className="library-group-kind">{libraryGroupLabel(group.id, group.description)}</span>}<strong>{group.name}</strong></span>{group.date && <span className="library-group-date">{group.date.slice(0, 10).replaceAll('-', '.')}</span>}<span className="library-group-count">{group.tracks.length + group.outfit_references.length}</span><ChevronDown size={19} /></button>
        {openGroup === group.id && <div className="library-group-panel" id={`group-${encodeURIComponent(group.id)}`}>{group.description && <p style={{ margin: '0 0 12px', fontSize: 12, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>{group.description}</p>}<div className="library-tracks">{group.outfit_references.map(reference => <button className="library-outfit-reference" key={reference.outfit_id} onClick={() => onOpenOutfit(reference.outfit_id)}><img src={reference.cover} alt="" /><strong>{reference.name}</strong><span>秘纹旋律</span></button>)}{group.tracks.map(t => t.mixer ? <InfinityTowerMixer key={t.id} track={t} onPlay={playTrack} /> : <div className="library-track-entry" key={t.id} data-content-id={t.id}><button className={`library-track ${selected?.id === t.id ? 'selected' : ''}`} onClick={() => playTrack(t)}><strong><MusicTitle title={t.title} />{t.description && <small style={{ display: 'block', fontSize: 12, fontWeight: 400, opacity: .8, whiteSpace: 'pre-wrap' }}>{t.description}</small>}</strong><span>{t.duration_seconds > 0 ? time(t.duration_seconds) : '--:--'}</span>{selected?.id === t.id && playback.playing ? <AudioLines size={18} /> : <Play size={18} />}</button></div>)}</div></div>}
      </section>)}{search && !visibleGroups.length && <p className="library-empty">没有找到音乐</p>}</div>
    </main>
    {selected && playback.trackId === selected.id && <section className="library-playback story-player" aria-label="音乐播放控制"><strong><MusicTitle title={selected.title} scrollingSubtitle /></strong><div className="story-playback-buttons"><button className="icon-button" aria-label="上一曲" disabled={queue.length < 2} onClick={() => skip(-1)}><SkipBack size={19} fill="currentColor" /></button><button className="play-button" aria-label={playback.playing ? '暂停播放' : '播放音乐'} disabled={playback.loading} onClick={() => void player.toggle()}>{playback.loading ? <LoaderCircle className="spinner" /> : playback.playing ? <Pause /> : <Play />}</button><button className="icon-button" aria-label="下一曲" disabled={queue.length < 2} onClick={() => skip(1)}><SkipForward size={19} fill="currentColor" /></button></div><span className="story-position">{time(playback.position)}</span><input className="seek" aria-label="播放进度" type="range" min="0" max={playback.duration || 1} step=".05" value={playback.position} onChange={e => player.seek(Number(e.target.value))} style={{ '--progress': `${playback.position / (playback.duration || 1) * 100}%` } as CSSProperties} /><span className="story-duration">{time(playback.duration)}</span><PlaybackModeButton className="story-loop" /></section>}
    {playback.error && <p className="audio-error" role="alert">{playback.error}</p>}
  </div>;
}
function App() {
  const [page, setPage] = useState<Page>(readPage);
  const [archiveKey, setArchiveKey] = useState(0);
  useEffect(()=>{if(page==='home')document.title='星塔旋律';},[page]);
  useEffect(() => { const change = (event?:Event) => { const next = readPage(); setPage(next); if (next === 'outfit' && event?.type !== 'music-routes-ready') setArchiveKey(k => k + 1); }; window.addEventListener('popstate', change); window.addEventListener('hashchange', change); window.addEventListener('music-routes-ready',change); return () => { window.removeEventListener('popstate', change); window.removeEventListener('hashchange', change); window.removeEventListener('music-routes-ready',change); }; }, []);
  const navigate = (next: Page, discId?: number) => {
    if (readStorage('nova-sfx', true)) void player.sound(next === 'home' ? 'ui_common_back' : 'ui_common_menu');
    const url = new URL(location.href); url.pathname='/'; url.hash = next === 'home' ? '' : `/${next}`;
    if (next !== 'outfit') url.searchParams.delete('disc');
    if (next !== 'library') { url.searchParams.delete('track'); url.searchParams.delete('mix'); }
    if (discId) url.searchParams.set('disc', String(discId));
    history.pushState(discId ? { from: 'library' } : null, '', url); setPage(next);
    if (discId) setArchiveKey(k => k + 1);
  };
  return <><div hidden={page !== 'outfit'}><ArchiveApp key={archiveKey} active={page === 'outfit'} fromStory={history.state?.from === 'library'} onBack={() => { if (history.state?.from === 'library') history.back(); else navigate('home'); }} /></div>
    {page === 'home' && <div className="app home-page"><div className="room-background" /><div className="room-haze" /><header className="topbar"><div className="title-ribbon"><img src="/ui/zs_top_title.png" alt="" /><h1>星塔旋律</h1></div></header><main className="home-stage"><nav className="home-sections" aria-label="音乐分类">{SECTIONS.map((section, i) => <button className={`home-section home-${section.id}`} key={section.id} onClick={() => navigate(section.id)} style={{ '--index': i } as CSSProperties}><div className="home-icon"><img src={section.icon} alt="" /></div><span>{section.name}</span><i className="home-entry-arrow" aria-hidden="true" /></button>)}</nav></main><footer className="home-disclaimer">不定期更新 | 版权归属：上海悠星网络科技有限公司 | 本站与悠星网络无关 | <a href="https://github.com/rikumi/nova-rhythm" target="_blank" rel="noopener noreferrer">GitHub</a></footer></div>}
    <div hidden={page !== 'library'}><MusicLibrary active={page === 'library'} onBack={() => navigate('home')} onOpenOutfit={id => navigate('outfit', id)} /></div>
  </>;
}
createRoot(document.getElementById('root')!).render(<App />);
