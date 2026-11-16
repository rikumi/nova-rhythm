const CACHE='nova-rhythm-shell-v2';
const SHELL=['/','/manifest.webmanifest','/icons/icon-192.png','/icons/icon-512.png'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('nova-rhythm-shell-') && key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
async function remember(request,response) {
  if(!response.ok)return response;
  try {
  const cache=await caches.open(CACHE);
  await cache.put(request,response.clone());
  const keys=await cache.keys();
  const optional=keys.filter(key=>!SHELL.some(path=>new URL(key.url).pathname===path));
  await Promise.all(optional.slice(0,Math.max(0,optional.length-100)).map(key=>cache.delete(key)));
  } catch { /* A storage quota or unavailable cache must not discard a network response. */ }
  return response;
}
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  // Never intercept or cache audio, byte ranges, artwork collections or third-party requests.
  if(request.method!=='GET' || url.origin!==self.location.origin || request.headers.has('range') || url.pathname.startsWith('/audio/') || url.pathname.startsWith('/art/'))return;
  if(request.mode==='navigate') {
    event.respondWith(fetch(request).then(async response=>{
      if(response.ok && url.pathname==='/'){try {const cache=await caches.open(CACHE);await cache.put('/',response.clone());} catch {/* optional */}}
      return response;
    }).catch(async()=>await caches.match('/') || Response.error()));
  } else if(url.pathname.startsWith('/data/') || url.pathname==='/manifest.webmanifest') {
    event.respondWith(fetch(request).then(response=>remember(request,response)).catch(async()=>await caches.match(request) || Response.error()));
  } else if(['/assets/','/fonts/','/ui/','/icons/'].some(prefix=>url.pathname.startsWith(prefix))) {
    event.respondWith(caches.match(request).catch(()=>undefined).then(cached=>cached || fetch(request).then(response=>remember(request,response))));
  }
});
