
window.addEventListener("offline", () => {
  console.log("Offline mode");
});

import { openDB } from "idb";

export const dbPromise = openDB("transsflow_offline", 1, {
  upgrade(db) {
    db.createObjectStore("queue", { keyPath: "id" });
  },
});

export async function enqueueEvent(event) {
  const db = await dbPromise;
  await db.put("queue", {
    ...event,
    status: "PENDING",
    created_at: new Date().toISOString(),
  });
}

export async function getPendingEvents() {
  const db = await dbPromise;
  return db.getAllFromIndex("queue", "status", "PENDING");
}

export async function markEventStatus(id, status) {
  const db = await dbPromise;
  const evt = await db.get("queue", id);
  evt.status = status;
  await db.put("queue", evt);
}

export async function queueSubmission(payload) {
  const db = await dbPromise;

  await db.put("queue", {
    local_id: crypto.randomUUID(),
    submission_id: payload.submission_id,
    payload,
    status: "PENDING",
    retries: 0,
    last_attempt_at: null,
  });
}



export async function syncQueue() {
  const db = await dbPromise;
  const tx = db.transaction("queue", "readwrite");
  const store = tx.objectStore("queue");

  const all = await store.getAll();

  for (const entry of all) {
    if (entry.status === "SYNCED") continue;

    try {
      const res = await fetch("/api/sync/submit/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry.payload),
      });

      if (!res.ok) throw new Error("Sync failed");

      entry.status = "SYNCED";
      entry.last_attempt_at = new Date().toISOString();
      await store.put(entry);
    } catch (e) {
      entry.retries += 1;
      entry.last_attempt_at = new Date().toISOString();
      await store.put(entry);
    }
  }
}


function updateStatus() {
  const el = document.getElementById("net-status");
  if (!el) return;

  if (navigator.onLine) {
    el.textContent = "● Online";
    el.className = "online";
  } else {
    el.textContent = "● Offline";
    el.className = "offline";
  }
}

window.addEventListener("online", updateStatus);
window.addEventListener("offline", updateStatus);
updateStatus();