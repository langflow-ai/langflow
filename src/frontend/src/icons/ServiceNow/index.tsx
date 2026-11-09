import { forwardRef, type SVGProps } from "react";

// The compact mark comes from the official ServiceNow header logo.
// https://www.servicenow.com/content/dam/now-www/en-us/images/global-nav/logo/servicenow-header-logo.svg
type IconProps = SVGProps<SVGSVGElement> & { isDark?: boolean };

export const ServiceNowIcon = forwardRef<SVGSVGElement, IconProps>(
  ({ isDark: _isDark, ...props }, ref) => (
    <svg
      ref={ref}
      viewBox="95 5 16 15"
      fill="#81b5a1"
      fillRule="evenodd"
      clipRule="evenodd"
      {...props}
    >
      <path d="m102.8 5.762c-4.2 0-7.5 3.3-7.5 7.5 0 2.2 0.9 4.2 2.3 5.6 0.5 0.5 1.4 0.5 2 0.1 0.8-0.7 2-1.1 3.2-1.1 1.3 0 2.3 0.4 3.2 1.1 0.6 0.5 1.4 0.4 2-0.2 1.4-1.4 2.3-3.3 2.3-5.5-0.1-4.1-3.4-7.5-7.5-7.5m-0.1 11.4c-2.3 0-3.8-1.7-3.8-3.8s1.5-3.8 3.8-3.8 3.8 1.7 3.8 3.8-1.5 3.8-3.8 3.8" />
    </svg>
  ),
);
