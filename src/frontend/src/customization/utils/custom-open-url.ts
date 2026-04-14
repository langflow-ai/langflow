// This file contains a utility function to open a URL in a new tab with security features enabled.
export function customOpenUrl(url: string): void {
  window.open(url, "_blank", "noopener,noreferrer");
}
