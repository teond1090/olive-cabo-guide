/* Olive - Great American West. Offline service worker.
   Cache-first for the app shell AND Olive's voice clips, so the whole guide
   plus every spoken line works with no signal - which is most of this route.
   Network-first for live data (weather, chat), which is useless when stale. */
const CACHE="olive-west-v17";   /* bumped: film looks, hearts, lightbox, captions, best-of */
const TILES="olive-tiles-v1";
const SHARE="olive-share-v1";   /* photos handed to Olive from the phone's own Photos app */
const TILE_MAX=1200;   /* roughly 60-90MB of map, plenty for this route */
const SHELL=["./","./index.html","./manifest.json"];
const VOICE=[
  "./voice/air.mp3",
  "./voice/altitude.mp3",
  "./voice/arrive.mp3",
  "./voice/bear.mp3",
  "./voice/bison.mp3",
  "./voice/boardwalk.mp3",
  "./voice/briefing.mp3",
  "./voice/bucket.mp3",
  "./voice/clearance.mp3",
  "./voice/food.mp3",
  "./voice/fuel.mp3",
  "./voice/fuel-gap.mp3",
  "./voice/gem.mp3",
  "./voice/goat.mp3",
  "./voice/heat.mp3",
  "./voice/landmark.mp3",
  "./voice/meds.mp3",
  "./voice/offline.mp3",
  "./voice/pass.mp3",
  "./voice/stars.mp3",
  "./voice/state.mp3",
  "./voice/storm.mp3",
  "./voice/stretch.mp3",
  "./voice/sunset.mp3",
  "./voice/video.mp3",
  "./voice/voice-on.mp3",
  "./voice/water.mp3",
  "./voice/wildlife.mp3",
  "./voice/wolf.mp3"
];

self.addEventListener("install",e=>{
  e.waitUntil((async()=>{
    const c=await caches.open(CACHE);
    await c.addAll(SHELL);
    /* voice clips are ~2.5MB - add them individually so one failure
       cannot abort the whole install */
    await Promise.all(VOICE.map(u=>c.add(u).catch(()=>{})));
    self.skipWaiting();
  })());
});
self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys()
    .then(ks=>Promise.all(ks.filter(k=>k!==CACHE&&k!==TILES&&k!==SHARE).map(k=>caches.delete(k))))
    .then(()=>self.clients.claim()));
});
self.addEventListener("fetch",e=>{
  const req=e.request;
  const url=new URL(req.url);

  /* ---- photos shared in from the phone's own Photos app ----
     Android delivers a share as a POST to this path. Stash the files where
     the page can collect them, then redirect back into Olive - a share must
     never dead-end on a blank page. There is no network involved, so this
     works with no signal, which is most of this route. */
  if(req.method==="POST"&&url.pathname.endsWith("/share")){
    e.respondWith((async()=>{
      try{
        const fd=await req.formData();
        const files=fd.getAll("photos").filter(f=>f&&f.size);
        const c=await caches.open(SHARE);
        for(const k of await c.keys())await c.delete(k);      /* last share only */
        let i=0;
        for(const f of files){
          await c.put(
            new Request("./__shared/"+(i++)+"?name="+encodeURIComponent(f.name||"photo.jpg")),
            new Response(f,{headers:{"Content-Type":f.type||"application/octet-stream"}})
          );
        }
      }catch(err){}
      return Response.redirect("./?shared=1",303);
    })());
    return;
  }

  if(req.method!=="GET")return;

  /* map tiles: cache-first and keep them, so the roads you have driven
     are still on the map when the signal goes. Trimmed when it gets big. */
  if(/tile\.openstreetmap\.org|server\.arcgisonline\.com|basemaps\.cartocdn\.com/.test(url.hostname)){
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

  /* live services: always try the network, never serve a stale answer */
  if(/ntfy\.sh|open-meteo\.com|air-quality-api/.test(url.hostname)){
    e.respondWith(fetch(req).catch(()=>new Response("",{status:503})));
    return;
  }
  /* the page itself: network first so updates land, cache as the fallback */
  if(req.mode==="navigate"||url.pathname.endsWith("index.html")){
    e.respondWith(
      fetch(req).then(r=>{const cp=r.clone();caches.open(CACHE).then(c=>c.put(req,cp));return r})
                .catch(()=>caches.match(req).then(r=>r||caches.match("./index.html")))
    );
    return;
  }
  /* everything else, voice clips included: cache first */
  e.respondWith(
    caches.match(req).then(hit=>hit||fetch(req).then(r=>{
      if(r.ok&&url.origin===location.origin){const cp=r.clone();caches.open(CACHE).then(c=>c.put(req,cp))}
      return r;
    }).catch(()=>new Response("",{status:503})))
  );
});
