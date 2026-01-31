import React, { forwardRef } from "react";
import HarvestIconSVG from "./harvest";

export const HarvestIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <HarvestIconSVG ref={ref} {...props} />;
});
