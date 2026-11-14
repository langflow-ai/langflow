import { forwardRef, type SVGProps } from "react";
import SvgTrustedRouter from "./TrustedRouterIcon";

type TrustedRouterIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const TrustedRouterIcon = forwardRef<
  SVGSVGElement,
  TrustedRouterIconProps
>(({ isDark: _isDark, ...props }, ref) => (
  <SvgTrustedRouter ref={ref} {...props} />
));
