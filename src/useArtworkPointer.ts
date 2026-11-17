import { useCallback, useEffect, useRef } from 'react';
import type { RefObject } from 'react';
import { ARTWORK_MOTION_GAIN } from './artworkMotion';

interface Bounds {left:number;top:number;width:number;height:number;}
function logicalBounds(element:HTMLElement,root:HTMLElement,rootBox:DOMRect):Bounds {
  let left=0,top=0,node:HTMLElement|null=element;
  while(node&&node!==root){left+=node.offsetLeft;top+=node.offsetTop;node=node.offsetParent as HTMLElement|null;}
  if(node!==root)return element.getBoundingClientRect();
  return {left:rootBox.left+left,top:rootBox.top+top,width:element.offsetWidth,height:element.offsetHeight};
}

export function useArtworkPointer(host:RefObject<HTMLDivElement|null>,light:RefObject<HTMLDivElement|null>){
  const geometry=useRef<{input:Bounds;light:Bounds}|null>(null);
  const pending=useRef<Record<string,string>|null>(null),frame=useRef(0);
  const reset=useCallback(()=>{geometry.current=null;},[]);
  useEffect(()=>{
    const element=host.current,root=element?.closest<HTMLElement>('.live-card')||element;
    const observer=new ResizeObserver(reset);
    if(root)observer.observe(root);if(element&&element!==root)observer.observe(element);
    window.addEventListener('scroll',reset,{capture:true,passive:true});window.addEventListener('resize',reset);
    return()=>{observer.disconnect();window.removeEventListener('scroll',reset,true);window.removeEventListener('resize',reset);cancelAnimationFrame(frame.current);};
  },[host,reset]);
  const sample=useCallback((point:{clientX:number;clientY:number})=>{
    const element=host.current,illumination=light.current;
    if(!element)return {x:0,y:0,active:false};
    if(!geometry.current){
      const root=element.closest<HTMLElement>('.live-card')||element,box=root.getBoundingClientRect();
      geometry.current={input:logicalBounds(element,root,box),light:logicalBounds(illumination||element,root,box)};
    }
    const {input,light:bounds}=geometry.current;
    const inside=point.clientX>=bounds.left&&point.clientX<=bounds.left+bounds.width&&point.clientY>=bounds.top&&point.clientY<=bounds.top+bounds.height;
    pending.current={'--light-x':`${Math.round((point.clientX-bounds.left)/Math.max(1,bounds.width)*1000)/10}%`,
      '--light-y':`${Math.round((point.clientY-bounds.top)/Math.max(1,bounds.height)*1000)/10}%`,'--light-active':inside?'1':'0'};
    if(!frame.current)frame.current=requestAnimationFrame(()=>{
      frame.current=0;
      if(light.current&&pending.current)for(const [name,value] of Object.entries(pending.current))
        if(light.current.style.getPropertyValue(name)!==value)light.current.style.setProperty(name,value);
      pending.current=null;
    });
    return {x:ARTWORK_MOTION_GAIN*Math.max(-1,Math.min(1,2*(point.clientX-input.left)/Math.max(1,input.width)-1)),
      y:ARTWORK_MOTION_GAIN*Math.max(-1,Math.min(1,2*(point.clientY-input.top)/Math.max(1,input.height)-1)),active:true};
  },[host,light]);
  const hide=useCallback(()=>{
    pending.current=null;cancelAnimationFrame(frame.current);frame.current=0;
    light.current?.style.setProperty('--light-active','0');geometry.current=null;
  },[light]);
  return {sample,hide,reset};
}
