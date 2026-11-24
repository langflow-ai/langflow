import { forwardRef, type SVGProps } from "react";
import SvgWorldRouter from "./WorldRouterIcon";

type WorldRouterIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const WorldRouterIcon = forwardRef<SVGSVGElement, WorldRouterIconProps>(
  ({ isDark: _isDark, ...props }, ref) => (
    <SvgWorldRouter ref={ref} {...props} />
  ),
);
