/**
 * Radix Popover moves focus into the content when it opens. For the model and
 * db-provider dropdowns — cmdk lists that have no CommandInput — the default
 * lands on the first focusable element, which is a footer action button
 * (Refresh / Manage providers) rather than the option list. That's the wrong
 * entry point for a listbox and makes the list feel unreachable by keyboard.
 *
 * Use as the Popover content's `onOpenAutoFocus` handler: it redirects initial
 * focus to the currently-selected option (or the first enabled one), so the
 * flow becomes open → list → Tab → footer buttons. cmdk marks its active item
 * with aria-selected, so this keeps DOM focus aligned with cmdk's highlight and
 * lets arrow keys continue navigating from there. Options carry no tabindex, so
 * a transient tabindex="-1" is added to make them programmatically focusable.
 *
 * No-ops (leaving Radix's default focus) when no option is present, so an empty
 * list still behaves sanely.
 */
export function focusCommandListOnOpen(event: Event): void {
  const content = event.currentTarget as HTMLElement | null;
  const list = content?.querySelector<HTMLElement>("[cmdk-list]");
  if (!list) return;

  const option =
    list.querySelector<HTMLElement>(
      '[role="option"][aria-selected="true"]:not([aria-disabled="true"])',
    ) ??
    list.querySelector<HTMLElement>(
      '[role="option"]:not([aria-disabled="true"])',
    );
  if (!option) return;

  event.preventDefault();
  if (option.getAttribute("tabindex") === null) {
    option.setAttribute("tabindex", "-1");
  }
  option.focus();
}
