let mo = null;
let scrollHandler = null;

function getNavbarHeight() {
  return document.querySelector(".navbar")?.clientHeight ?? 0;
}

function syncPassed() {
  const links = Array.from(document.querySelectorAll(".table-of-contents__link"));
  if (!links.length) return;

  let forceLastActive = false;
  const lastLink = links[links.length - 1];
  const lastHref = lastLink?.getAttribute("href");

  if (lastHref) {
    const lastHeading = document.querySelector(lastHref);
    if (lastHeading) {
      const rect = lastHeading.getBoundingClientRect();
      const navH = getNavbarHeight();
      const headingVisible = rect.top >= navH && rect.top < window.innerHeight;
      const atMaxScroll = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 50;

      if (headingVisible && atMaxScroll) {
        forceLastActive = true;
      }
    }
  }

  // Pause observer to avoid mutation loop
  if (mo) mo.disconnect();

  if (forceLastActive) {
    links.forEach((l, i) => {
      if (i === links.length - 1) {
        l.classList.add("table-of-contents__link--active");
        l.dataset.tocForced = "1";
      } else {
        l.classList.remove("table-of-contents__link--active");
      }
    });
  } else if (lastLink.dataset.tocForced) {
    delete lastLink.dataset.tocForced;
  }

  const activeIdx = links.findIndex((l) =>
    l.classList.contains("table-of-contents__link--active")
  );

  links.forEach((l, i) =>
    l.classList.toggle("table-of-contents__link--passed", i < activeIdx && activeIdx !== -1)
  );

  // Reconnect observer
  const toc = document.querySelector(".table-of-contents");
  if (toc && mo) {
    mo.observe(toc, { attributes: true, subtree: true, attributeFilter: ["class"] });
  }
}

export function onRouteDidUpdate() {
  if (typeof window === "undefined") return;

  if (mo) mo.disconnect();
  if (scrollHandler) window.removeEventListener("scroll", scrollHandler);

  // Initialize observer
  const toc = document.querySelector(".table-of-contents");
  if (toc) {
    mo = new MutationObserver(syncPassed);
    mo.observe(toc, { attributes: true, subtree: true, attributeFilter: ["class"] });
  }

  // Scroll handler with RAF throttle
  let raf = null;
  scrollHandler = () => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = null;
      syncPassed();
    });
  };
  window.addEventListener("scroll", scrollHandler, { passive: true });

  requestAnimationFrame(syncPassed);
}
