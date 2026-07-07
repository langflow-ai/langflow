import { useEffect } from "react";

type InertEntry = {
  hadInert: boolean;
  owners: Set<symbol>;
};

const inertEntries = new Map<HTMLElement, InertEntry>();

function releaseOwner(owner: symbol, element: HTMLElement) {
  const entry = inertEntries.get(element);
  if (!entry) return;

  entry.owners.delete(owner);
  if (entry.owners.size > 0) return;

  if (!entry.hadInert) {
    element.removeAttribute("inert");
  }
  inertEntries.delete(element);
}

function syncInertElements(owner: symbol) {
  inertEntries.forEach((_entry, element) => {
    if (element.getAttribute("data-aria-hidden") !== "true") {
      releaseOwner(owner, element);
    }
  });

  document
    .querySelectorAll<HTMLElement>('[data-aria-hidden="true"]')
    .forEach((element) => {
      const entry = inertEntries.get(element) ?? {
        hadInert: element.hasAttribute("inert"),
        owners: new Set<symbol>(),
      };
      entry.owners.add(owner);
      inertEntries.set(element, entry);
      element.setAttribute("inert", "");
    });
}

function releaseAllOwnedElements(owner: symbol) {
  Array.from(inertEntries.keys()).forEach((element) => {
    releaseOwner(owner, element);
  });
}

export function useInertForAriaHiddenElements() {
  useEffect(() => {
    const owner = Symbol("dialog-inert-owner");
    const sync = () => syncInertElements(owner);

    sync();
    const frame = requestAnimationFrame(sync);

    const observer = new MutationObserver(sync);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-aria-hidden"],
    });

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      releaseAllOwnedElements(owner);
    };
  }, []);
}
