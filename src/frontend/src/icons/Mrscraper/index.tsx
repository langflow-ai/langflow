import type React from "react";
import { forwardRef } from "react";
import SvgMrscraperLogo from "./MrscraperIcon";

export const MrscraperIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMrscraperLogo ref={ref} {...props} />;
});
