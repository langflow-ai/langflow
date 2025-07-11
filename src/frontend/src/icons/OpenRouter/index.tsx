import type React from "react";
import { forwardRef } from "react";
import SvgOpenRouter from "./OpenRouterIcon";

export const OpenRouterIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOpenRouter ref={ref} {...props} />;
});
