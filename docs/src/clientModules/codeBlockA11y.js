// Docusaurus renders code blocks as <pre tabindex="0"> unconditionally.
// IBM Equal Access (element_tabbable_role_valid) exempts tabbable elements
// only when they actually scroll — a non-scrollable <pre> with tabindex fails.
// Scrollable blocks get the scrollable-region pattern (role + unique name);
// non-scrollable blocks lose the needless tabindex.

function updateCodeBlocks() {
  const pres = document.querySelectorAll("pre.prism-code");
  let index = 0;
  for (const pre of pres) {
    index += 1;
    const scrollable =
      pre.scrollWidth > pre.clientWidth || pre.scrollHeight > pre.clientHeight;
    if (scrollable) {
      pre.setAttribute("tabindex", "0");
      pre.setAttribute("role", "region");
      pre.setAttribute("aria-label", `Code sample ${index}`);
    } else {
      pre.removeAttribute("tabindex");
      pre.removeAttribute("role");
      pre.removeAttribute("aria-label");
    }
  }
}

let observer;
let resizeTimer;

export function onRouteDidUpdate() {
  if (typeof document === "undefined") {
    return;
  }
  updateCodeBlocks();
  if (!observer) {
    observer = new MutationObserver(updateCodeBlocks);
    // childList: re-rendered code blocks arrive without the attributes.
    // attributeFilter "hidden": Docusaurus tabs toggle panels via the hidden
    // attribute (no childList mutation) — a scrollable block inside an
    // initially hidden tab measures scrollWidth 0 and loses its tabindex, so
    // it must be re-evaluated when its tab becomes visible. The patched
    // attributes (tabindex/role/aria-label) are not observed — no feedback loop.
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["hidden"],
    });
    // Scrollability is viewport-dependent — re-evaluate on resize.
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(updateCodeBlocks, 250);
    });
  }
}
