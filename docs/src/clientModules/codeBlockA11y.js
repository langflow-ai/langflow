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
    // Tab switches re-render code blocks without the attributes — re-apply.
    observer = new MutationObserver(updateCodeBlocks);
    observer.observe(document.body, { childList: true, subtree: true });
    // Scrollability is viewport-dependent — re-evaluate on resize.
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(updateCodeBlocks, 250);
    });
  }
}
