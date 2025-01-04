import React, { forwardRef } from "react";
import Tavily from "./Tavily";

export const TavilyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <Tavily ref={ref} {...props} />;
});
