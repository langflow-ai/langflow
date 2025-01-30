import React, { forwardRef } from "react";
import GridGainSVG from "./GridGain";

export const GridGain = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GridGainSVG ref={ref} {...props} />;
});