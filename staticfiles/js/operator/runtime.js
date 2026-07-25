import { queueSubmission } from "./offline.js";

document.getElementById("runtimeForm").onsubmit = e => {
  e.preventDefault();
  alert("Submitted (offline/online handled by backend)");
};


async function submitOffline(formData) {
  const payload = {
    submission_id: formData.submission_id,
    template_code: formData.template_code,
    work_context_id: formData.work_context_id,
    responses: formData.responses,
    submitted_at: new Date().toISOString(),
  };

  await queueSubmission(payload);

  alert("Saved offline. Will sync automatically.");
}


import { enqueueEvent } from "./offline.js";

document.querySelector("form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = new FormData(e.target);
  const data = Object.fromEntries(payload.entries());

  await enqueueEvent({
    id: crypto.randomUUID(),
    type: "SUBMISSION_SUBMIT",
    payload: data,
  });

  alert("Saved offline. Will sync when online.");
});