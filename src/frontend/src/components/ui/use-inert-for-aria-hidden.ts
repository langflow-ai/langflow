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

function claimInert(owner: symbol, element: HTMLElement) {
  const entry = inertEntries.get(element) ?? {
    hadInert: element.hasAttribute("inert"),
    owners: new Set<symbol>(),
  };
  entry.owners.add(owner);
  inertEntries.set(element, entry);
  element.setAttribute("inert", "");
}

/**
 * Radix Select's hideOthers() marks the page (including the open combobox
 * trigger) with aria-hidden / data-aria-hidden. IBM requires that combobox
 * to stay focusable (combobox_focusable_elements) and not sit under
 * aria-hidden (aria_hidden_nontabbable). Unwrap those attrs on the open
 * combobox's ancestor path so both rules can pass.
 */
function unwrapHiddenAncestorsOfOpenCombobox(owner: symbol) {
  document
    .querySelectorAll<HTMLElement>('[role="combobox"][aria-expanded="true"]')
    .forEach((combobox) => {
      let node: HTMLElement | null = combobox;
      while (node && node !== document.body) {
        if (
          node.getAttribute("data-aria-hidden") === "true" ||
          node.getAttribute("aria-hidden") === "true"
        ) {
          node.removeAttribute("aria-hidden");
          node.removeAttribute("data-aria-hidden");
          releaseOwner(owner, node);
        }
        node = node.parentElement;
      }
    });
}

function syncInertElements(owner: symbol) {
  unwrapHiddenAncestorsOfOpenCombobox(owner);

  const claimed = new Set<HTMLElement>();

  document
    .querySelectorAll<HTMLElement>('[data-aria-hidden="true"]')
    .forEach((element) => {
      claimInert(owner, element);
      claimed.add(element);
    });

  inertEntries.forEach((_entry, element) => {
    if (!claimed.has(element)) {
      releaseOwner(owner, element);
    }
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
      attributeFilter: ["data-aria-hidden", "aria-hidden", "aria-expanded"],
    });

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      releaseAllOwnedElements(owner);
    };
  }, []);
}
