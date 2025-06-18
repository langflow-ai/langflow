import React, { forwardRef } from "react";
import PerplexitySVG from "./Perplexity";

export const PerplexityIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <PerplexitySVG ref={ref} {...props} />;
});
