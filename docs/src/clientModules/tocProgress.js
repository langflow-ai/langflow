// Marks TOC links above the active one as --passed (scroll progress).
// Uses a module-scoped observer so it's properly disconnected on re-navigation.

function syncPassed() {
  const links = Array.from(
    document.querySelectorAll(".table-of-contents__link")
  );
  const activeIdx = links.findIndex((l) =>
    l.classList.contains("table-of-contents__link--active")
  );
  links.forEach((l, i) =>
    l.classList.toggle("table-of-contents__link--passed", i < activeIdx)
  );
}

let mo = null;

export function onRouteDidUpdate() {
  if (typeof window === "undefined") return;
  if (mo) {
    mo.disconnect();
    mo = null;
  }
  syncPassed();
  const toc = document.querySelector(".table-of-contents");
  if (!toc) return;
  mo = new MutationObserver(syncPassed);
  mo.observe(toc, { attributes: true, subtree: true, attributeFilter: ["class"] });
}
