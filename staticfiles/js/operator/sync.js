import { getPendingEvents, markEventStatus } from "./offline.js";

async function syncOnce() {
  const events = await getPendingEvents();

  for (const evt of events) {
    try {
      await markEventStatus(evt.id, "SYNCING");

      const res = await fetch("/api/offline/ingest/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(evt),
      });

      if (!res.ok) throw new Error("Sync failed");

      await markEventStatus(evt.id, "DONE");
    } catch (err) {
      await markEventStatus(evt.id, "FAILED");
    }
  }
}

window.addEventListener("online", syncOnce);
setInterval(syncOnce, 30000);
