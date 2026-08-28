import type React from "react";
import { forwardRef } from "react";
import SvgIFlytek from "./IFlytekIcon";

export const IFlytekIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>(({ isDark: _isDark, ...props }, ref) => (
  <SvgIFlytek ref={ref} {...props} />
));
