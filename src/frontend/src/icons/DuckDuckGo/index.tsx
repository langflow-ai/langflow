import type React from "react";
import { forwardRef } from "react";
import SvgDuckDuckGo from "./DuckDuckGo";

export const DuckDuckGoIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ color?: string }>
>((props, ref) => {
  return <SvgDuckDuckGo ref={ref} {...props} />;
});
