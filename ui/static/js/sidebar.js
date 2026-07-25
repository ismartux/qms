/* static/js/sidebar.js */

// ======================
// DROPDOWN TOGGLE
// ======================
function toggleNavDropdown(el) {
  const dropdown = el.closest('.nav-dropdown');
  const isOpen = dropdown.classList.contains('open');

  document.querySelectorAll('.nav-dropdown').forEach(d => {
    d.classList.remove('open');
    d.querySelectorAll('.approval-parent-badge, .capa-parent-badge')
      .forEach(b => b.classList.remove('hidden'));
  });

  if (!isOpen) {
    dropdown.classList.add('open');
    dropdown.querySelectorAll('.approval-parent-badge, .capa-parent-badge')
      .forEach(b => b.classList.add('hidden'));
  }
}

// ======================
// AUTO-OPEN ACTIVE MENU
// ======================
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-sub-item.active').forEach(item => {
    const dropdown = item.closest('.nav-dropdown');
    if (!dropdown) return;

    dropdown.classList.add('open');
    dropdown.querySelectorAll('.approval-parent-badge, .capa-parent-badge')
      .forEach(b => b.classList.add('hidden'));
  });
});

window.toggleNavDropdown = toggleNavDropdown;


document.addEventListener("DOMContentLoaded", () => {
  const tooltip = document.getElementById("globalTooltip");
  const sidebar = document.getElementById("sidebar");

  document.querySelectorAll(
    ".sidebar .nav-item[data-tooltip], \
     .sidebar .nav-sub-item[data-tooltip], \
     .sidebar .sidebar-user[data-tooltip]"
  ).forEach(item => {

    item.addEventListener("mouseenter", () => {
      if (!sidebar.classList.contains("collapsed")) return;

      tooltip.textContent = item.dataset.tooltip;
      tooltip.style.opacity = "1";

      const rect = item.getBoundingClientRect();
      tooltip.style.left = rect.right + 12 + "px";
      tooltip.style.top = rect.top + rect.height / 2 + "px";
      tooltip.style.transform = "translateY(-50%)";
    });

    item.addEventListener("mouseleave", () => {
      tooltip.style.opacity = "0";
    });
  });
});