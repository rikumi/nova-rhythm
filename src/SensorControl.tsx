import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Smartphone } from 'lucide-react';
import { deviceTilt } from './deviceTilt';
import './sensorControl.css';

export function SensorControl({full=false}:{full?:boolean}){
  const sensor=useSyncExternalStore(deviceTilt.subscribe,deviceTilt.snapshot);
  const [open,setOpen]=useState(false),root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null);
  useEffect(()=>{
    if(!open)return;
    const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target))setOpen(false);};
    document.addEventListener('pointerdown',outside);
    root.current?.querySelector<HTMLButtonElement>('[role=option][aria-selected=true]')?.focus();
    return()=>document.removeEventListener('pointerdown',outside);
  },[open]);
  if(!sensor.mobile||!sensor.supported)return null;
  const enabled=sensor.status==='enabled';
  return <>
    <div ref={root} className="capsule-toggle sensor-control" data-enabled={enabled}>
      <button className="sensor-enable" aria-label={enabled?'关闭重力感应':'开启重力感应'} title={enabled?'关闭重力感应':'开启重力感应'} aria-pressed={enabled} disabled={sensor.status==='requesting'} onClick={()=>{if(enabled)deviceTilt.disable();else void deviceTilt.enable();}}>
        <span className="capsule-checkbox" aria-hidden="true"/>{full?<Smartphone size={21}/>:sensor.status==='requesting'?'授权中':sensor.status==='denied'?'重试感应':'重力感应'}
      </button>
      <button ref={trigger} className="sensor-direction-trigger" aria-label="重力感应方向" aria-haspopup="listbox" aria-expanded={open} onClick={()=>setOpen(value=>!value)} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();setOpen(true);}}}>{sensor.direction==='reverse'?'反向':'原版'}</button>
      {open&&<div className="sensor-direction-menu" role="listbox" aria-label="重力感应方向" onKeyDown={event=>{
        if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setOpen(false);trigger.current?.focus();}
        if(event.key==='ArrowDown'||event.key==='ArrowUp'){
          event.preventDefault();const options=[...event.currentTarget.querySelectorAll<HTMLButtonElement>('[role=option]')],index=options.indexOf(document.activeElement as HTMLButtonElement);
          options[(index+(event.key==='ArrowDown'?1:-1)+options.length)%options.length]?.focus();
        }
      }}>
        {(['original','reverse'] as const).map(direction=><button key={direction} role="option" aria-selected={sensor.direction===direction} onClick={()=>{deviceTilt.setDirection(direction);setOpen(false);trigger.current?.focus();}}>{direction==='reverse'?'反向':'原版'}</button>)}
      </div>}
    </div>
    {sensor.error&&<span role="status" style={full?{position:'fixed',top:80,right:20,maxWidth:'calc(100vw - 40px)',fontSize:12,padding:'8px 12px',background:'#142440e6'}:{flexBasis:'100%',textAlign:'center',fontSize:12}}>{sensor.error}</span>}
  </>;
}
