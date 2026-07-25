/* static/js/app.js */

// ======================
// STATE
// ======================
const appState = {
  sidebarCollapsed: localStorage.getItem('sidebar-collapsed') === 'true',
  isMobile: window.innerWidth < 1024,
  userDropdownOpen: false,
  deferredPrompt: null,
  registration: null,
  installPromptShown: localStorage.getItem('install-prompt-shown') === 'true',
  isFirstVisit: !localStorage.getItem('hasVisited'),
};

// ======================
// DOM ELEMENTS
// ======================
const elements = {
  sidebar: document.getElementById('sidebar'),
  overlay: document.querySelector('.sidebar-overlay'),
  toggleBtn: document.getElementById('desktopToggle'),
  body: document.body,
  userDropdown: document.getElementById('userDropdown'),
  dropdownArrow: document.getElementById('dropdownArrow'),
  pwaLoading: document.getElementById('pwaLoading'),
};

// ======================
// SIDEBAR
// ======================
function toggleSidebar() {
  if (appState.isMobile) {
    const isActive = elements.sidebar.classList.contains('active');
    elements.sidebar.classList.toggle('active');
    elements.overlay?.classList.toggle('active');
    elements.body.classList.toggle('sidebar-open');
    elements.body.style.overflow = !isActive ? 'hidden' : '';
  } else {
    elements.sidebar.classList.toggle('collapsed');
    localStorage.setItem(
      'sidebar-collapsed',
      elements.sidebar.classList.contains('collapsed')
    );
    updateToggleButtonIcon();
  }
}

function updateToggleButtonIcon() {
  if (!elements.toggleBtn) return;
  const icon = elements.toggleBtn.querySelector('i');
  if (!icon) return;

  if (appState.isMobile || elements.sidebar.classList.contains('collapsed')) {
    icon.className = 'fas fa-bars text-gray-700 text-lg';
  } else {
    icon.className = 'fas fa-times text-gray-700 text-lg';
  }
}

function initializeSidebar() {
  appState.isMobile = window.innerWidth < 1024;

  if (!appState.isMobile && appState.sidebarCollapsed) {
    elements.sidebar.classList.add('collapsed');
  }

  if (appState.isMobile) {
    elements.sidebar.classList.remove('collapsed');
  }

  updateToggleButtonIcon();
}

// ======================
// CLOSE SIDEBAR (MOBILE SAFE)
// ======================
function closeMobileSidebar() {
  if (!appState.isMobile) return;

  if (elements.sidebar.classList.contains('active')) {
    elements.sidebar.classList.remove('active');
    elements.overlay?.classList.remove('active');
    document.body.classList.remove('sidebar-open');
    document.body.style.overflow = '';
  }
}

// ======================
// USER DROPDOWN
// ======================
function toggleUserDropdown() {
  appState.userDropdownOpen = !appState.userDropdownOpen;

  elements.userDropdown.classList.toggle('active', appState.userDropdownOpen);
  elements.dropdownArrow.style.transform = appState.userDropdownOpen
    ? 'rotate(180deg)'
    : 'rotate(0deg)';

  if (appState.userDropdownOpen) {
    setTimeout(() => document.addEventListener('click', closeUserDropdownOutside), 50);
  } else {
    document.removeEventListener('click', closeUserDropdownOutside);
  }
}

function closeUserDropdown() {
  appState.userDropdownOpen = false;
  elements.userDropdown.classList.remove('active');
  elements.dropdownArrow.style.transform = 'rotate(0deg)';
  document.removeEventListener('click', closeUserDropdownOutside);
}

function closeUserDropdownOutside(e) {
  if (!elements.userDropdown.contains(e.target)) {
    closeUserDropdown();
  }
}

// ======================
// PWA + SERVICE WORKER
// ======================
function registerServiceWorker() {
  localStorage.setItem('hasVisited', 'true');

  const fallback = setTimeout(() => {
    elements.pwaLoading?.classList.add('hidden');
  }, 3000);

  if (!('serviceWorker' in navigator)) {
    clearTimeout(fallback);
    elements.pwaLoading?.classList.add('hidden');
    return;
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register(window.APP_CONFIG.serviceWorkerUrl)
      .finally(() => {
        clearTimeout(fallback);
        elements.pwaLoading?.classList.add('hidden');
      });
  });
}

// ======================
// INSTALL PROMPT
// ======================
function setupInstallPrompt() {
  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    appState.deferredPrompt = e;
  });
}

function installApp() {
  if (!appState.deferredPrompt) return;

  appState.deferredPrompt.prompt();
  appState.deferredPrompt = null;
}

// ======================
// EVENTS
// ======================
window.addEventListener('resize', () => {
  const wasMobile = appState.isMobile;
  appState.isMobile = window.innerWidth < 1024;

  if (wasMobile !== appState.isMobile) {
    initializeSidebar();
  }
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeUserDropdown();
    if (appState.isMobile && elements.sidebar.classList.contains('active')) {
      toggleSidebar();
    }
  }
});

// ======================
// INIT
// ======================
document.addEventListener('DOMContentLoaded', () => {
  initializeSidebar();
  registerServiceWorker();
  setupInstallPrompt();

  $('.select2').select2({ minimumResultsForSearch: 5 });
  $('.modern-select').select2({
    width: '100%',
    placeholder: 'Select Role',
    allowClear: true,
  });
  // ✅ Close sidebar when clicking overlay
  elements.overlay?.addEventListener('click', closeMobileSidebar);

  // ✅ Close sidebar when clicking mobile nav blocker
  const mobileBlocker = document.getElementById('mobileNavBlocker');
  mobileBlocker?.addEventListener('click', closeMobileSidebar);
});

// ======================
// GLOBAL EXPORTS
// ======================
window.toggleSidebar = toggleSidebar;
window.toggleUserDropdown = toggleUserDropdown;
window.closeUserDropdown = closeUserDropdown;
window.installApp = installApp;

function mountModal(html) {
  const root = document.getElementById("modal-root");
  root.innerHTML = html;
}