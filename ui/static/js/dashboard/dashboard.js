fetch("/api/analytics")
  .then(r => r.json())
  .then(data => {
    document.getElementById("dashboard").innerText =
      JSON.stringify(data, null, 2);
  });
