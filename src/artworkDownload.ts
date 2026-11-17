import type { MouseEvent } from 'react';

export async function downloadArtwork(event: MouseEvent<HTMLAnchorElement>): Promise<void> {
  if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  const link=event.currentTarget;
  // Cross-origin Raw links ignore the HTML download attribute. A same-origin
  // blob URL preserves the existing save action and the original PNG filename.
  if(new URL(link.href).origin===location.origin)return;
  event.preventDefault();
  if(link.dataset.downloading)return;
  link.dataset.downloading='true';link.setAttribute('aria-busy','true');
  let url: string | undefined;
  try{
    const response=await fetch(link.href);
    if(!response.ok)throw new Error('Artwork download failed');
    url=URL.createObjectURL(await response.blob());
    const download=document.createElement('a');download.href=url;download.download=link.download;
    document.body.append(download);download.click();download.remove();
  }catch{
    // Retain the original link as a fallback if the image host is unavailable.
    const fallback=document.createElement('a');fallback.href=link.href;fallback.target='_blank';fallback.rel='noopener';fallback.click();
  }finally{
    delete link.dataset.downloading;link.removeAttribute('aria-busy');
    if(url){const finished=url;setTimeout(()=>URL.revokeObjectURL(finished),1000);}
  }
}
