// Marks TOC links above the active one as --passed (scroll progress).

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

export function onRouteDidUpdate() {
  if (typeof window === "undefined") return;
  syncPassed();
  const toc = document.querySelector(".table-of-contents");
  if (!toc) return;
  const mo = new MutationObserver(syncPassed);
  mo.observe(toc, { attributes: true, subtree: true, attributeFilter: ["class"] });
  return () => mo.disconnect();
}
