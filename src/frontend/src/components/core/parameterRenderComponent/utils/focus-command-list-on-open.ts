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
