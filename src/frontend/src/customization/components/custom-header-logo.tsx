import LangflowLogo from "@/assets/LangflowLogo.svg?react";

/**
 * Seam for the mark inside the header's home button.
 *
 * OSS renders the Langflow logo. A distribution replaces this file when its
 * brand guidelines govern what may appear in a product header — some forbid
 * using the application icon as a logo there — without forking AppHeader.
 *
 * The button around it owns the navigation and the accessible name, so this
 * renders decoration only and stays `aria-hidden`.
 */
export function CustomHeaderLogo({ className }: { className?: string }) {
  return <LangflowLogo className={className} aria-hidden="true" />;
}

export default CustomHeaderLogo;
