/* Chris in Littleton - offline service worker.
   Scoped to /chris/ only, so it never touches the Olive app at the root.
   Cache-first for the app shell and the map tiles Chris has already seen;
   network-first for anything live (weather, chat, the friends map), which
   is worse than useless when it is stale. */
const CACHE="chris-v5";   /* bumped: bingo, postcards, diary, ask-Clara */
const TILES="chris-tiles-v1";
const TILE_MAX=900;                /* roughly the Denver metro at street zoom */
const SHELL=["./","./index.html","./manifest.json"];

self.addEventListener("install",e=>{
  e.waitUntil((async()=>{
    const c=await caches.open(CACHE);
    /* individually, so one miss cannot abort the whole install */
    await Promise.all(SHELL.map(u=>c.add(u).catch(()=>{})));
    self.skipWaiting();
  })());
});

self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys()
    .then(ks=>Promise.all(ks.filter(k=>k.startsWith("chris-")&&k!==CACHE&&k!==TILES&&k!=="chris-tts-v1").map(k=>caches.delete(k))))
    .then(()=>self.clients.claim()));
});

self.addEventListener("fetch",e=>{
  const req=e.request;
  if(req.method!=="GET")return;
  const url=new URL(req.url);

  /* map tiles: keep what she has already seen, so the friends map still
     draws in a canyon. Trimmed once the cache gets fat. */
  if(/tile\.openstreetmap\.org/.test(url.hostname)){
    e.respondWith((async()=>{
      const c=await caches.open(TILES);
      const hit=await c.match(req);
      if(hit)return hit;
      try{
        const r=await fetch(req);
        if(r.ok){
          c.put(req,r.clone());
          const keys=await c.keys();
          if(keys.length>TILE_MAX)await Promise.all(keys.slice(0,keys.length-TILE_MAX).map(k=>c.delete(k)));
        }
        return r;
      }catch(err){return new Response("",{status:504})}
    })());
    return;
  }

  /* live services: always the network, never a stale answer */
  if(/ntfy\.sh|open-meteo\.com|air-quality-api|overpass|elevenlabs\.io/.test(url.hostname)){
    e.respondWith(fetch(req).catch(()=>new Response("",{status:503})));
    return;
  }

  /* the page itself: network first so updates land, cache as the fallback */
  if(req.mode==="navigate"||url.pathname.endsWith("/chris/index.html")){
    e.respondWith(
      fetch(req).then(r=>{const cp=r.clone();caches.open(CACHE).then(c=>c.put(req,cp));return r})
                .catch(()=>caches.match(req).then(r=>r||caches.match("./index.html")))
    );
    return;
  }

  /* everything else: cache first */
  e.respondWith(
    caches.match(req).then(hit=>hit||fetch(req).then(r=>{
      if(r.ok&&url.origin===location.origin){const cp=r.clone();caches.open(CACHE).then(c=>c.put(req,cp))}
      return r;
    }).catch(()=>new Response("",{status:503})))
  );
});
