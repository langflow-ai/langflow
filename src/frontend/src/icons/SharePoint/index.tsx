import type React from "react";
import { forwardRef } from "react";
import SvgSharePoint from "./SharePoint";

type SharePointIconProps = React.SVGProps<SVGSVGElement> & { isDark?: boolean };

export const SharePointIcon = forwardRef<SVGSVGElement, SharePointIconProps>(
  ({ isDark: _isDark, ...props }, ref) => (
    <SvgSharePoint ref={ref} {...props} />
  ),
);
