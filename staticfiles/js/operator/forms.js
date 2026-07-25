fetch("/api/forms")
  .then(r => r.json())
  .then(data => {
    const el = document.getElementById("formsList");
    data.forEach(f => {
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `<a href="/app/forms/${f.code}">${f.name}</a>`;
      el.appendChild(div);
    });
  });
