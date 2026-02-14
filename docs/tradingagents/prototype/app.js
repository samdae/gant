// ===== GANT — Frontend App (v2) =====

// ── Router ──
const routes = {
  "/": "page-dashboard",
  "/positions": "page-positions",
  "/schedules": "page-schedules",
  "/trade": "page-trade",
  "/archive": "page-archive",
  "/live": "page-live",
  "/search": "page-search",
};

function getRoute() {
  const hash = location.hash.slice(1) || "/";
  if (hash.startsWith("/trade/"))
    return { route: "/trade", param: hash.split("/")[2] };
  if (hash.startsWith("/archive/"))
    return { route: "/archive", param: hash.split("/")[2] };
  return { route: hash, param: null };
}

function navigate() {
  const { route, param } = getRoute();
  const pageId = routes[route] || routes["/"];

  // Switch pages
  document
    .querySelectorAll(".page")
    .forEach((p) => p.classList.remove("active"));
  const target = document.getElementById(pageId);
  if (target) target.classList.add("active");

  // Update desktop nav
  document.querySelectorAll(".nav-link[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });

  // Update bottom nav
  document.querySelectorAll(".bottom-nav-item[data-route]").forEach((item) => {
    item.classList.toggle("active", item.dataset.route === route);
  });

  // Update drawer nav
  document.querySelectorAll(".drawer-link[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });

  // Parameterized pages
  if (route === "/trade" && param) {
    document.getElementById("tradeTickerTitle").textContent =
      `${param.toUpperCase()} 거래`;
    // Update archive link
    const archiveBtn = document.getElementById("viewArchiveBtn");
    if (archiveBtn) archiveBtn.href = `#/archive/${param}`;
  }
  if (route === "/archive" && param) {
    document.getElementById("archiveTickerTitle").textContent =
      `${param.toUpperCase()} 아카이브`;
  }

  closeDrawer();
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", navigate);
window.addEventListener("DOMContentLoaded", () => {
  if (!location.hash) location.hash = "#/";
  navigate();
});

// ── Mobile Drawer (kept for fallback) ──
const drawerOverlay = document.getElementById("drawerOverlay");
const mobileDrawer = document.getElementById("mobileDrawer");
const drawerClose = document.getElementById("drawerClose");

function openDrawer() {
  drawerOverlay.classList.add("open");
  mobileDrawer.classList.add("open");
}
function closeDrawer() {
  drawerOverlay.classList.remove("open");
  mobileDrawer.classList.remove("open");
}

drawerOverlay.addEventListener("click", closeDrawer);
drawerClose.addEventListener("click", closeDrawer);

// ── Tabs ──
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    btn
      .closest(".tab-bar")
      .querySelectorAll(".tab-btn")
      .forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    // Find sibling tab contents
    const container = btn.closest(".tab-bar").parentElement;
    container
      .querySelectorAll(".tab-content")
      .forEach((tc) => tc.classList.add("hidden"));
    const tabTarget = document.getElementById(`tab-${tab}`);
    if (tabTarget) tabTarget.classList.remove("hidden");
  });
});

// ── Modals ──
function showModal(id) {
  document.getElementById(id).classList.remove("hidden");
}
function hideModal(id) {
  document.getElementById(id).classList.add("hidden");
}

// Add Schedule
document.getElementById("addScheduleBtn").addEventListener("click", () => showModal("addModal"));
document.getElementById("addModalClose").addEventListener("click", () => hideModal("addModal"));
document.getElementById("addModalCancel").addEventListener("click", () => hideModal("addModal"));
document.getElementById("addModalSubmit").addEventListener("click", () => {
  hideModal("addModal");
});

// Delete Schedule
document.querySelectorAll(".schedule-delete").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const ticker = btn
      .closest(".schedule-card")
      .querySelector(".ticker-badge").textContent;
    document.getElementById("deleteTickerName").textContent = ticker;
    showModal("deleteModal");
  });
});
document.getElementById("deleteModalClose").addEventListener("click", () => hideModal("deleteModal"));
document.getElementById("deleteModalCancel").addEventListener("click", () => hideModal("deleteModal"));
document.getElementById("deleteModalConfirm").addEventListener("click", () => hideModal("deleteModal"));

// Token
document.getElementById("tokenModalClose").addEventListener("click", () => hideModal("tokenModal"));
document.getElementById("tokenModalCancel").addEventListener("click", () => hideModal("tokenModal"));
document.getElementById("tokenModalSave").addEventListener("click", () => hideModal("tokenModal"));

// Close modals on overlay click
document.querySelectorAll(".modal-overlay").forEach((overlay) => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.classList.add("hidden");
  });
});

// ── Search ──
const searchBtn = document.getElementById("searchBtn");
const searchInput = document.getElementById("searchInput");

searchBtn?.addEventListener("click", () => {
  const query = searchInput?.value.trim();
  if (query) {
    // Results are already visible by default
  }
});

searchInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchBtn?.click();
});

// ── Keyboard shortcuts ──
document.addEventListener("keydown", (e) => {
  // Escape closes modals/drawer
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-overlay:not(.hidden)").forEach((m) => {
      m.classList.add("hidden");
    });
    closeDrawer();
  }
});
