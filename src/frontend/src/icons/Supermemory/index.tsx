import { forwardRef, type SVGProps } from "react";
import Supermemory from "./Supermemory";

type SupermemoryIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The glyph is drawn with currentColor, so it follows the theme and isDark is
// accepted but not needed.
export const SupermemoryIcon = forwardRef<SVGSVGElement, SupermemoryIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Supermemory ref={ref} {...props} />,
);
