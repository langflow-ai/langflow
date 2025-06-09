import React, { forwardRef } from "react";
import SvgBrightData from "./Brightdata.svg";

export const BrightDataIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgBrightData ref={ref} {...props} />;
});
