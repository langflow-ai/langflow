import { forwardRef, type SVGProps } from "react";
import Piloterr from "./Piloterr";

type PiloterrIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The brand mark keeps its colours on light and dark backgrounds, so isDark is
// accepted but not needed.
export const PiloterrIcon = forwardRef<SVGSVGElement, PiloterrIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Piloterr ref={ref} {...props} />,
);
