import React, { forwardRef } from "react";
import BrightdataIconSVG from "./brightdata";

export const BrightdataIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <BrightdataIconSVG ref={ref} {...props} />;
});
