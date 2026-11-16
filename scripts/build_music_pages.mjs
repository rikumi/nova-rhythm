import { readFile,mkdir,writeFile } from 'node:fs/promises';
import { resolve,join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { resolveStoryLibrary } from '../src/storyLibrary.ts';
import { musicPath,musicRouteSegment,outfitMusicPage,storyMusicPage } from '../src/musicRoutes.ts';

export function collectMusicPages(mapping,metadata,outfits) {
  const library=resolveStoryLibrary(mapping,metadata);
  const names=new Map(library.groups.map(group=>[group.id,group.name]));
  const pages=library.tracks.map(track=>storyMusicPage(track,names.get(track.group_id)||'星塔唱片'));
  pages.push(...outfits.items.flatMap(outfit=>outfit.music.map((music,index)=>outfitMusicPage(outfit,music,index))));
  if(new Set(pages.map(page=>page.id)).size!==pages.length)throw new Error('Duplicate music IDs across published collections');
  return pages;
}
const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
export function renderMusicPage(template,page,origin) {
  const url=new URL(musicPath(page.id),origin).href;
  const audio=new URL(page.audio,origin).href,image=new URL(page.image,origin).href;
  const description='星塔旋律 · '+page.collection;
  const extension=new URL(audio).pathname.split('.').at(-1).toLowerCase();
  const mime=({opus:'audio/ogg',ogg:'audio/ogg',mp3:'audio/mpeg',m4a:'audio/mp4',wav:'audio/wav',flac:'audio/flac'})[extension]||'application/octet-stream';
  const meta={
    'og:type':'music.song','og:title':page.title,'og:description':description,'og:site_name':'星塔旋律','og:locale':'zh_CN',
    'og:url':url,'og:image':image,'og:image:secure_url':image,'og:audio':audio,'og:audio:secure_url':audio,'og:audio:type':mime,
    'music:duration':String(Math.round(page.duration)),
  };
  for(const [key,value] of Object.entries({width:page.imageWidth,height:page.imageHeight,type:page.imageType}))if(value!==undefined)meta['og:image:'+key]=String(value);
  const tags=Object.entries(meta).map(([property,content])=>`    <meta property="${property}" content="${escape(content)}" />`).join('\n');
  const serialized=value=>JSON.stringify(value).replaceAll('<','\\u003c').replaceAll('>','\\u003e').replaceAll('&','\\u0026');
  const jsonld={'@context':'https://schema.org','@type':'AudioObject',name:page.title,description,
    url,contentUrl:audio,encodingFormat:mime,duration:`PT${Math.round(page.duration*1000)/1000}S`,thumbnailUrl:image,
    isPartOf:{'@type':page.kind==='outfit'?'MusicAlbum':'CreativeWork',name:page.collection}};
  return template.replace(/<title>[^<]*<\/title>/,`<title>${escape(page.title)}</title>`)
    .replace(/<meta name="description"[^>]*>/,`<meta name="description" content="${escape(description)}" />`)
    .replace('</head>',`${tags}\n    <link rel="canonical" href="${escape(url)}" />\n    <link rel="alternate" type="${mime}" href="${escape(audio)}" title="${escape(page.title)}" />\n    <meta name="twitter:card" content="summary_large_image" />\n    <script id="music-page" type="application/json">${serialized(page)}</script>\n    <script type="application/ld+json">${serialized(jsonld)}</script>\n  </head>`);
}

async function main() {
  const source=resolve(process.env.NOVA_PUBLIC_DIR||'public'),output=resolve(process.env.NOVA_DIST_DIR||'dist');
  const read=async name=>JSON.parse(await readFile(join(source,'data',name),'utf8'));
  const [mapping,metadata,outfits,template]=await Promise.all([read('story-melodies.json'),read('library.json'),read('outfits.json'),readFile(join(output,'index.html'),'utf8')]);
  const origin=process.env.SITE_ORIGIN || 'https://'+(await readFile(join(source,'CNAME'),'utf8')).trim();
  const pages=collectMusicPages(mapping,metadata,outfits);
  for(const page of pages) {
    if(page.image.startsWith('/') && page.image.endsWith('.jpg')) {
      const data=await readFile(join(source,page.image.slice(1)));
      for(let offset=2;offset+8<data.length;) {
        if(data[offset]!==255)break;
        const marker=data[offset+1],length=data.readUInt16BE(offset+2);
        if([192,193,194].includes(marker)){page.imageHeight=data.readUInt16BE(offset+5);page.imageWidth=data.readUInt16BE(offset+7);break;}
        offset+=length+2;
      }
    }
    const folder=join(output,'music',musicRouteSegment(page.id));await mkdir(folder,{recursive:true});
    await writeFile(join(folder,'index.html'),renderMusicPage(template,page,origin),'utf8');
  }
  console.log(`Generated ${pages.length} static music pages with Open Graph audio and JSON-LD.`);
}
if(process.argv[1] && import.meta.url===pathToFileURL(resolve(process.argv[1])).href)await main();
