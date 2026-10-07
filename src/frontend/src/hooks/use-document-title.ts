import { useEffect } from "react";

export const APP_NAME = "Langflow";

/**
 * Builds the tab title for a page. Titles that already carry the product name
 * (e.g. the "Langflow API Keys" settings page) are used as-is so the tab does
 * not read "Langflow API Keys | Langflow".
 */
export function formatDocumentTitle(title?: string | null): string {
  const pageTitle = title?.trim();
  if (!pageTitle) return APP_NAME;
  return pageTitle.includes(APP_NAME)
    ? pageTitle
    : `${pageTitle} | ${APP_NAME}`;
}

/**
 * Names the browser tab after the page the calling component renders
 * (WCAG 2.4.2 Page Titled).
 *
 * Pass the same string the page shows as its heading. Pass a falsy value while
 * the name is still loading — the tab then shows the product name alone instead
 * of a stale one. The title resets on unmount, so a route that forgets to call
 * this never inherits the previous route's title.
 */
export function useDocumentTitle(title?: string | null): void {
  useEffect(() => {
    document.title = formatDocumentTitle(title);
    return () => {
      document.title = APP_NAME;
    };
  }, [title]);
}
