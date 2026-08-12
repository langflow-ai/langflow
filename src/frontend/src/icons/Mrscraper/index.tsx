import type React from "react";
import { forwardRef } from "react";
import SvgMrscraperLogo from "./MrscraperIcon";

export const MrscraperIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgMrscraperLogo ref={ref} {...props} />;
});
