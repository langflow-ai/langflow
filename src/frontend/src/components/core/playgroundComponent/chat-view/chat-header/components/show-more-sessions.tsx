import { useLayoutEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import type { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useAlertStore from "@/stores/alertStore";

export type SessionsPagination = Pick<
  ReturnType<typeof useGetSessionsFromFlowQuery>,
  "hasNextPage" | "isFetchingNextPage" | "fetchNextPage"
>;

// The focusable part of a session row: a menu item, or a sidebar row's button.
const FOCUSABLE_ROW = '[role="menuitem"], [role="button"][tabindex="0"]';

/**
 * Loads the next page of older sessions at the end of a session list, and
 * renders nothing once every page is loaded. It must be the list's last child,
 * right after the rows. Inside a dropdown menu pass `asMenuItem` so it joins the
 * menu's arrow-key navigation.
 */
export function ShowMoreSessions({
  pagination: { hasNextPage, isFetchingNextPage, fetchNextPage },
  asMenuItem = false,
}: {
  pagination: SessionsPagination;
  asMenuItem?: boolean;
}) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  // Set when the focused control requests the last page: the control then
  // disappears, and focus moves to the first row loaded below `anchor`.
  const pendingFocus = useRef<{ anchor: Element; waited: boolean } | null>(
    null,
  );

  // Runs after every render: the rows come from a store synced after the query
  // updates, so they can render one pass after the control disappears.
  useLayoutEffect(() => {
    const pending = pendingFocus.current;
    if (hasNextPage || !pending) return;
    // Only restore focus the control took with it (it fell to <body>); never
    // take it from wherever the user went while the page loaded.
    const active = document.activeElement;
    const focusLost = !active || active === document.body;
    const firstLoaded = pending.anchor.nextElementSibling;
    if (focusLost && !firstLoaded && !pending.waited) {
      pending.waited = true;
      return;
    }
    pendingFocus.current = null;
    if (!focusLost || !firstLoaded) return;
    const target = firstLoaded.matches(FOCUSABLE_ROW)
      ? firstLoaded
      : firstLoaded.querySelector(FOCUSABLE_ROW);
    if (target instanceof HTMLElement) target.focus();
  });

  if (!hasNextPage) return null;

  const loadMore = async (control: HTMLElement) => {
    if (isFetchingNextPage) return;
    const anchor = control.previousElementSibling;
    pendingFocus.current =
      anchor && control.contains(document.activeElement)
        ? { anchor, waited: false }
        : null;
    const result = await fetchNextPage();
    // The control stays (another page, or a retry after an error) and keeps
    // focus itself.
    if (result.hasNextPage) pendingFocus.current = null;
    if (result.isFetchNextPageError) {
      setErrorData({ title: t("errors.loadMoreSessions") });
    }
  };

  const label = t("chat.showMoreSessions");

  if (asMenuItem) {
    return (
      <DropdownMenuItem
        className="gap-2 text-sm text-muted-foreground"
        data-testid="show-more-sessions"
        aria-disabled={isFetchingNextPage || undefined}
        aria-busy={isFetchingNextPage || undefined}
        onSelect={(event) => {
          // Keep the menu open so the loaded sessions can be picked.
          event.preventDefault();
          if (event.currentTarget instanceof HTMLElement) {
            void loadMore(event.currentTarget);
          }
        }}
      >
        {isFetchingNextPage && (
          <ForwardedIconComponent
            name="Loader2"
            className="h-4 w-4 animate-spin"
            aria-hidden="true"
          />
        )}
        {label}
      </DropdownMenuItem>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-8 w-full justify-start px-2 font-normal text-muted-foreground"
      data-testid="show-more-sessions"
      loading={isFetchingNextPage}
      ignoreTitleCase
      onClick={(event) => void loadMore(event.currentTarget)}
    >
      {label}
    </Button>
  );
}
