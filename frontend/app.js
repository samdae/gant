// ===== GANT — Frontend App =====

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

  // Update nav
  document.querySelectorAll("[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });

  // Parameterized pages
  if (route === "/trade" && param) {
    document.getElementById("tradeTickerTitle").textContent =
      `${param.toUpperCase()} Trade`;
    // Update archive link
    const archiveBtn = document.getElementById("viewArchiveBtn");
    if (archiveBtn) archiveBtn.href = `#/archive/${param}`;
  }
  if (route === "/archive" && param) {
    document.getElementById("archiveTickerTitle").textContent =
      `${param.toUpperCase()} Archive`;
  }

  closeDrawer();
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", navigate);
window.addEventListener("DOMContentLoaded", () => {
  if (!location.hash) location.hash = "#/";
  navigate();
});

// ── Mobile Drawer ──
const menuBtn = document.getElementById("menuBtn");
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

menuBtn.addEventListener("click", openDrawer);
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
    const target = document.getElementById(`tab-${tab}`);
    if (target) target.classList.remove("hidden");
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
const searchResults = document.getElementById("searchResults");
const searchEmpty = document.getElementById("searchEmpty");

searchBtn?.addEventListener("click", () => {
  const query = searchInput?.value.trim();
  if (query) {
    searchEmpty.style.display = "none";
    searchResults.classList.add("visible");
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
