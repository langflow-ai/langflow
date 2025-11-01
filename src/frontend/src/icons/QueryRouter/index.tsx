import React, { forwardRef } from "react";
import SvgQueryRouter from "./QueryRouter";

export const QueryRouterIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgQueryRouter ref={ref} {...props} />;
});
