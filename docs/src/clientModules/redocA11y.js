// Accessibility patches for Redocusaurus pages.
//
// 1. Landmarks: Redoc renders its layout without <main>/<nav>, failing IBM
//    Equal Access "aria_content_in_landmark" for every element on the page.
// 2. Dark-theme response chip colors: success/error colors come from a single
//    Redoc theme (no per-color-mode option), so values tuned to pass WCAG AA
//    on light backgrounds fail on dark. Status is only distinguishable by
//    computed color (styled-components class hashes are unstable), so we
//    patch inline colors when the dark theme is active and undo on light.
//
// Tested against redocusaurus@2.5.0 / Redoc v2.x DOM.

// config colors.success.main / colors.error.main → dark-accessible variants
const DARK_COLOR_PATCHES = new Map([
  ["rgb(24, 106, 32)", "#22952d"], // success green #186a20
  ["rgb(206, 30, 27)", "#e74745"], // error red #ce1e1b
]);

const patched = [];
let observersStarted = false;

function applyLandmarks() {
  const redoc = document.querySelector(".redocusaurus");
  if (!redoc) {
    return false;
  }
  const api = redoc.querySelector(".api-content");
  const menu = redoc.querySelector(".menu-content");
  if (!api && !menu) {
    return false;
  }
  if (api && !api.getAttribute("role")) {
    api.setAttribute("role", "main");
  }
  if (menu && !menu.getAttribute("role")) {
    menu.setAttribute("role", "navigation");
    menu.setAttribute("aria-label", "API endpoints");
  }
  return true;
}

function patchDarkChipColors() {
  while (patched.length) {
    patched.pop().style.removeProperty("color");
  }
  if (document.documentElement.getAttribute("data-theme") !== "dark") {
    return;
  }
  const root = document.querySelector(".redocusaurus .api-content");
  if (!root) {
    return;
  }
  // Response chips render the status color on <strong> (code) and <p> (text);
  // selected status tabs use the same colors on <li>.
  for (const el of root.querySelectorAll("strong, p, li[data-rttab]")) {
    const fix = DARK_COLOR_PATCHES.get(getComputedStyle(el).color);
    if (fix) {
      el.style.setProperty("color", fix, "important");
      patched.push(el);
    }
  }
}

function patchRedocSemantics() {
  const redoc = document.querySelector(".redocusaurus");
  if (!redoc) {
    return;
  }
  // Decorative chevrons/arrows — Redoc ships them with no accessible name.
  for (const svg of redoc.querySelectorAll(
    "svg:not([aria-hidden]):not([aria-label]):not([role])"
  )) {
    svg.setAttribute("aria-hidden", "true");
  }
  // Content-type dropdowns render as bare <select> elements.
  for (const select of redoc.querySelectorAll(
    "select.dropdown-select:not([aria-label])"
  )) {
    select.setAttribute("aria-label", "Content type");
  }
  // Redoc lays out schema fields as 2-column <table>s (name | description)
  // with no <th> anywhere — they are layout tables, so take them out of
  // table semantics; content still reads in DOM order (name, description).
  // role="rowheader" on the name <td> is NOT valid ARIA inside a native table.
  for (const table of redoc.querySelectorAll("table:not([role])")) {
    if (!table.querySelector("th")) {
      table.setAttribute("role", "presentation");
    }
  }
}

function runPatches() {
  patchDarkChipColors();
  patchRedocSemantics();
}

export function onRouteDidUpdate({ location }) {
  // Only Redoc routes (/api, /api/workflow) — a bare startsWith("/api")
  // would also match regular docs pages like /api-request or /api-keys
  // and leak a body observer per navigation (Redoc never renders there).
  const isRedocPage =
    location.pathname === "/api" || location.pathname.startsWith("/api/");
  if (typeof document === "undefined" || !isRedocPage) {
    return;
  }
  // Redoc is server-side rendered, so this usually succeeds immediately;
  // fall back to observing until hydration creates the containers.
  if (!applyLandmarks()) {
    const observer = new MutationObserver(() => {
      if (applyLandmarks()) {
        observer.disconnect();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  runPatches();
  if (!observersStarted) {
    observersStarted = true;
    // Re-patch when the user toggles the color mode.
    new MutationObserver(patchDarkChipColors).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    // Redoc lazy-renders operations on scroll/expand — re-patch on changes.
    // Semantics patches are cheap/idempotent: run on the next frame so late
    // renders are covered immediately; the (heavier) color patch is debounced.
    let timer;
    let frameQueued = false;
    new MutationObserver(() => {
      if (!frameQueued) {
        frameQueued = true;
        window.requestAnimationFrame(() => {
          frameQueued = false;
          patchRedocSemantics();
        });
      }
      clearTimeout(timer);
      timer = setTimeout(runPatches, 300);
    }).observe(document.body, { childList: true, subtree: true });
  }
}
