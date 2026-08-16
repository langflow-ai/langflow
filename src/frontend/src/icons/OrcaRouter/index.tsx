import type React from "react";
import { forwardRef } from "react";
import SvgOrcaRouter from "./OrcaRouterIcon";

export const OrcaRouterIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOrcaRouter ref={ref} {...props} />;
});
