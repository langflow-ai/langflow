import React, { forwardRef } from "react";
import PerplexitySVG from "./perplexity";

export const PerplexityIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <PerplexitySVG ref={ref} {...props} />;
});
