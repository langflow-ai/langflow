// Adds ARIA landmarks to Redocusaurus pages — Redoc renders its layout
// without <main>/<nav> landmarks, which fails IBM Equal Access
// "aria_content_in_landmark" for every element on the page.
// Tested against redocusaurus@2.5.0 / Redoc v2.x DOM (.api-content / .menu-content).

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

export function onRouteDidUpdate({ location }) {
  if (typeof document === "undefined" || !location.pathname.startsWith("/api")) {
    return;
  }
  // Redoc is server-side rendered, so this usually succeeds immediately;
  // fall back to observing until hydration creates the containers.
  if (applyLandmarks()) {
    return;
  }
  const observer = new MutationObserver(() => {
    if (applyLandmarks()) {
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}
