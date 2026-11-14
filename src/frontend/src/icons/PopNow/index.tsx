import { forwardRef, type SVGProps } from "react";
import SvgPopNow from "./PopNowIcon";

type PopNowIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const PopNowIcon = forwardRef<SVGSVGElement, PopNowIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgPopNow ref={ref} {...props} />,
);
