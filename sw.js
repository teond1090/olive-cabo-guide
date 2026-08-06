/* Olive - Great American West. Offline service worker.
   Cache-first for the app shell so the whole guide works with no signal;
   network-first for live data (weather, chat) which is useless when stale. */
const CACHE="olive-west-v1";
const SHELL=["./","./index.html","./manifest.json"];

self.addEventListener("install",e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener("fetch",e=>{
  const req=e.request;
  if(req.method!=="GET")return;
  const url=new URL(req.url);

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
  /* everything else: cache first, fill in behind */
  e.respondWith(
    caches.match(req).then(hit=>hit||fetch(req).then(r=>{
      if(r.ok&&url.origin===location.origin){const cp=r.clone();caches.open(CACHE).then(c=>c.put(req,cp))}
      return r;
    }).catch(()=>new Response("",{status:503})))
  );
});
