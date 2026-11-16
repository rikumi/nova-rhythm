import { musicTitleParts } from './musicTitle.ts';

export interface MusicPage {
  id: string; kind: 'library' | 'outfit'; title: string; collection: string;
  audio: string; duration: number; image: string; outfitId?: number; melodyIndex?: number;
}
const routes=new Map<string,MusicPage>();
export function musicRouteSegment(id:string):string {
  if(/^[a-zA-Z0-9_-]+$/.test(id))return id;
  return '~'+btoa(String.fromCharCode(...new TextEncoder().encode(id))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
}
export function musicPath(id:string):string {return '/music/'+musicRouteSegment(id)+'/';}
export function musicIdFromPath(pathname:string):string|undefined {
  const match=/^\/music\/([^/]+)\/?$/.exec(pathname);
  if(!match)return;
  try {
    const segment=decodeURIComponent(match[1]);
    if(segment.startsWith('~'))return new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(atob(segment.slice(1).replaceAll('-','+').replaceAll('_','/')),char=>char.charCodeAt(0)));
    return segment;
  } catch{return;}
}
export function musicUrl(href:string,id:string):URL {
  const url=new URL(href);url.pathname=musicPath(id);url.hash='';
  for(const key of ['track','disc','mix'])url.searchParams.delete(key);
  return url;
}
export function registerMusicPages(pages:MusicPage[]):void {
  let changed=false;
  for(const page of pages)if(!routes.has(page.id)){routes.set(page.id,page);changed=true;}
  if(changed && typeof window!=='undefined')window.dispatchEvent(new Event('music-routes-ready'));
}
export function musicPage(id=musicIdFromPath(location.pathname)):MusicPage|undefined {
  if(!id)return;
  const known=routes.get(id);if(known)return known;
  try {
    const embedded=JSON.parse(document.getElementById('music-page')?.textContent||'null') as MusicPage|null;
    if(embedded?.id===id)return embedded;
  } catch{/* The normal catalog will resolve an unavailable embedded record. */}
}
export function outfitMusicPage(outfit:{id:number;name:string;staticImage:string},music:{id:string;title:string;display_title?:string;path:string;duration_seconds:number},index:number):MusicPage {
  return {id:music.id,kind:'outfit',outfitId:outfit.id,melodyIndex:index,
    title:music.display_title ? musicTitleParts(music.display_title).title : index===0 ? outfit.name : `${outfit.name} · ${music.title}`,
    collection:outfit.name,audio:music.path,duration:music.duration_seconds,image:outfit.staticImage};
}
export function storyMusicPage(track:{id:string;title:string;path:string;duration_seconds:number},collection:string):MusicPage {
  return {id:track.id,kind:'library',title:musicTitleParts(track.title).title,collection,audio:track.path,duration:track.duration_seconds,image:'/icons/icon-512.png'};
}
export function updateMusicPageMetadata(page:MusicPage):void {
  document.title=page.title;
  const description='星塔旋律 · '+page.collection;
  const audio=new URL(page.audio,location.origin).href;
  const mime=page.audio.split('?')[0].endsWith('.mp3') ? 'audio/mpeg' : page.audio.split('?')[0].endsWith('.m4a') ? 'audio/mp4' : 'audio/ogg';
  const values:Record<string,string>={'og:title':page.title,'og:description':description,'og:type':'music.song','og:site_name':'星塔旋律','og:url':new URL(musicPath(page.id),location.origin).href,'og:image':new URL(page.image,location.origin).href,'og:audio':audio,'og:audio:secure_url':audio,'og:audio:type':mime,'music:duration':String(Math.round(page.duration))};
  for(const [property,content] of Object.entries(values)) {
    let element=document.head.querySelector<HTMLMetaElement>(`meta[property="${property}"]`);
    if(!element){element=document.createElement('meta');element.setAttribute('property',property);document.head.append(element);}
    element.content=content;
  }
  const meta=document.head.querySelector<HTMLMetaElement>('meta[name=description]');if(meta)meta.content=description;
  let canonical=document.head.querySelector<HTMLLinkElement>('link[rel=canonical]');
  if(!canonical){canonical=document.createElement('link');canonical.rel='canonical';document.head.append(canonical);}
  canonical.href=new URL(musicPath(page.id),location.origin).href;
  let jsonld=document.head.querySelector<HTMLScriptElement>('script[type="application/ld+json"]');
  if(!jsonld){jsonld=document.createElement('script');jsonld.type='application/ld+json';document.head.append(jsonld);}
  jsonld.textContent=JSON.stringify({'@context':'https://schema.org','@type':'AudioObject',name:page.title,description,contentUrl:audio,encodingFormat:mime,duration:`PT${Math.round(page.duration*1000)/1000}S`});
}
