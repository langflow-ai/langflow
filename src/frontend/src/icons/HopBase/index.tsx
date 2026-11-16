import { forwardRef, type SVGProps } from "react";
import SvgHopBase from "./HopBaseIcon";

type HopBaseIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const HopBaseIcon = forwardRef<SVGSVGElement, HopBaseIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgHopBase ref={ref} {...props} />,
);
