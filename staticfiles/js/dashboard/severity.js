fetch("/api/analytics/severity")
  .then(res => res.json())
  .then(data => {
    renderSeverity(data.data)
  });

function renderSeverity(rows) {
  console.log("Severity data", rows);
}
