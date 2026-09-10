// cmdk moves its internal "highlighted" state (and aria-selected) on
// ArrowUp/ArrowDown/Home/End, but never moves real DOM focus with it — it
// expects either a focused CommandInput with aria-activedescendant, or the
// consumer to keep focus in sync itself. These lists have no CommandInput,
// so without this, keyboard navigation is silent for screen reader users
// even though the visual highlight (and Enter-to-select) still work.
//
// Also implements roving tabindex: exactly one option (the selected/
// highlighted one) is ever part of the page's Tab order at a time — every
// other option is programmatically focusable only (tabindex="-1"). Without
// this, none of the options have a tabindex at all by default, so Tab (or
// Shift+Tab back in from the footer buttons below the list) skips the
// entire list instead of landing on the current selection.
function focusSelectedCommandItem(list: HTMLElement | null): void {
  if (!list) return;

  const options = Array.from(
    list.querySelectorAll<HTMLElement>('[role="option"]'),
  );
  const target =
    options.find(
      (opt) =>
        opt.getAttribute("aria-selected") === "true" &&
        opt.getAttribute("aria-disabled") !== "true",
    ) ?? options.find((opt) => opt.getAttribute("aria-disabled") !== "true");
  if (!target) return;

  for (const option of options) {
    option.setAttribute("tabindex", option === target ? "0" : "-1");
  }
  target.focus();
}

export function focusCommandListOnOpen(event: Event): void {
  const content = event.currentTarget as HTMLElement | null;
  const list = content?.querySelector<HTMLElement>("[cmdk-list]");
  if (!list) return;

  event.preventDefault();
  focusSelectedCommandItem(list);
}

const NAVIGATION_KEYS = new Set(["ArrowDown", "ArrowUp", "Home", "End"]);

export function refocusSelectedCommandItemOnNavigate(
  event: React.KeyboardEvent<HTMLElement>,
): void {
  if (!NAVIGATION_KEYS.has(event.key)) return;
  const list = event.currentTarget.querySelector<HTMLElement>("[cmdk-list]");
  if (!list) return;

  requestAnimationFrame(() => focusSelectedCommandItem(list));
}
