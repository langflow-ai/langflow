import type React from "react";
import { forwardRef } from "react";
import SvgFortytwo from "./FortytwoIcon";

interface FortytwoIconProps extends React.SVGProps<SVGSVGElement> {
  isDark?: boolean;
}

export const FortytwoIcon = forwardRef<SVGSVGElement, FortytwoIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgFortytwo ref={ref} {...props} />,
);
