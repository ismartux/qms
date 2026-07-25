fetch("/api/analytics/pareto")
  .then(res => res.json())
  .then(data => {
    renderPareto(data.data)
  });

function renderPareto(rows) {
  console.log("Pareto data", rows);
  // chart.js / echarts / d3 later
}
