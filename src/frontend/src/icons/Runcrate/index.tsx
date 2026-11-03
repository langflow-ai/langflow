import { forwardRef, type SVGProps } from "react";
import SvgRuncrate from "./RuncrateIcon";

type RuncrateIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The SVG uses currentColor, so isDark is accepted and not forwarded.
export const RuncrateIcon = forwardRef<SVGSVGElement, RuncrateIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgRuncrate ref={ref} {...props} />,
);
