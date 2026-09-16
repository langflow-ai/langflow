import type React from "react";
import { forwardRef } from "react";
import SvgAnonRouter from "./AnonRouterIcon";

type AnonRouterIconProps = React.SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const AnonRouterIcon = forwardRef<SVGSVGElement, AnonRouterIconProps>(
  ({ isDark: _isDark, ...props }, ref) => {
    return <SvgAnonRouter ref={ref} {...props} />;
  },
);

AnonRouterIcon.displayName = "AnonRouterIcon";
