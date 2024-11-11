import React, { forwardRef } from "react";
import SvgZepMemory from "./ZepMemory";

export const ZepMemoryIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgZepMemory ref={ref} {...props} />;
});
