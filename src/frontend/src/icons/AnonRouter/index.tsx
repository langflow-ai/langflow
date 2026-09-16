import type React from "react";
import { forwardRef } from "react";
import SvgAnonRouter from "./AnonRouterIcon";

export const AnonRouterIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAnonRouter ref={ref} {...props} />;
});
