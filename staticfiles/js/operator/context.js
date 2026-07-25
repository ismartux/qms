const contextForm = document.getElementById("contextForm");

contextForm.onsubmit = e => {
  e.preventDefault();

  const context = {
    plant_id: plant.value,
    line_id: line.value,
    product_id: product.value
  };

  localStorage.setItem("execution_context", JSON.stringify(context));
  fetch("/api/context/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(context)
  });

  window.location.href = "/app/forms";
};
