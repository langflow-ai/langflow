import React, { forwardRef } from "react";
import GridGainSVG from "./GridGain";

export const GridGainIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GridGainSVG ref={ref} {...props} />;
});
