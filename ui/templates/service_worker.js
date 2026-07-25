/* ======================================================
   CACHE NAMES
   ====================================================== */
const STATIC_CACHE = "transsflow-static";
const API_CACHE = "transsflow-api";
const OFFLINE_PAGE = "/offline/";
const API_URL = "/api/";

/* ======================================================
   INSTALL
   - Cache ONLY offline fallback
   - Do NOT hard-cache static assets
   ====================================================== */
self.addEventListener("install", event => {
  console.log("Service Worker: Installing");
  self.skipWaiting();

  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => {
      return cache.addAll([OFFLINE_PAGE]);
    })
  );
});

/* ======================================================
   ACTIVATE
   - Clean old caches
   ====================================================== */
self.addEventListener("activate", event => {
  console.log("Service Worker: Activating");

  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(name => {
          if (![STATIC_CACHE, API_CACHE].includes(name)) {
            console.log("Deleting old cache:", name);
            return caches.delete(name);
          }
        })
      );
    })
  );

  self.clients.claim();
});

/* ======================================================
   FETCH
   ====================================================== */
self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);

  // Ignore chrome-extension
  if (url.protocol === "chrome-extension:") return;

  /* ---------------- HTML NAVIGATION ---------------- */
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_PAGE))
    );
    return;
  }

  /* ---------------- API REQUESTS (NETWORK FIRST) ---------------- */
  if (url.pathname.startsWith(API_URL)) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.status === 200) {
            const clone = response.clone();
            caches.open(API_CACHE).then(cache => {
              cache.put(request, clone);
            });
          }
          return response;
        })
        .catch(() =>
          caches.match(request).then(res => {
            if (res) return res;
            return new Response(
              JSON.stringify({
                error: "Offline",
                message: "You are currently offline."
              }),
              { status: 503, headers: { "Content-Type": "application/json" } }
            );
          })
        )
    );
    return;
  }

  /* ---------------- STATIC FILES (NETWORK FIRST) ---------------- */
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      fetch(request)
        .then(response => {
          const clone = response.clone();
          caches.open(STATIC_CACHE).then(cache => {
            cache.put(request, clone);
          });
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }
});

/* ======================================================
   BACKGROUND SYNC
   ====================================================== */
self.addEventListener("sync", event => {
  if (event.tag === "sync-queue") {
    console.log("Service Worker: Background sync triggered");
    event.waitUntil(syncPendingActions());
  }
});

/* ======================================================
   PUSH NOTIFICATIONS
   ====================================================== */
self.addEventListener("push", event => {
  console.log("Service Worker: Push received");

  const options = {
    body: event.data ? event.data.text() : "New notification from Transs Flow",
    icon: "/static/icons/icon-192x192.png",
    badge: "/static/icons/badge-72x72.png",
    vibrate: [100, 50, 100],
    data: { dateOfArrival: Date.now() },
    actions: [
      { action: "explore", title: "Explore" },
      { action: "close", title: "Close" }
    ]
  };

  event.waitUntil(
    self.registration.showNotification("Transs Flow IPQC", options)
  );
});

/* ======================================================
   NOTIFICATION CLICK
   ====================================================== */
self.addEventListener("notificationclick", event => {
  event.notification.close();

  if (event.action === "explore") {
    event.waitUntil(clients.openWindow("/"));
  }
});

/* ======================================================
   SYNC HELPERS (UNCHANGED LOGIC)
   ====================================================== */
async function syncPendingActions() {
  try {
    const db = await openDB("ipqc-queue", 1);
    const pendingActions = await db.getAll("actions");

    for (const action of pendingActions) {
      try {
        await fetch(action.endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${action.token}`
          },
          body: JSON.stringify(action.data)
        });
        await db.put("actions", { ...action, status: "synced" });
      } catch {
        await db.put("actions", { ...action, status: "failed" });
      }
    }
  } catch (err) {
    console.error("Sync error:", err);
  }
}

function openDB(name, version) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, version);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = event => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains("actions")) {
        db.createObjectStore("actions", { keyPath: "id", autoIncrement: true });
      }
    };
  });
}

/* ======================================================
   MESSAGE HANDLER
   ====================================================== */
self.addEventListener("message", event => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});