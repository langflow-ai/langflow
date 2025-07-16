import React, { forwardRef } from "react";
import SvgCleanlab from "./Cleanlab";

export const CleanlabIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCleanlab ref={ref} {...props} />;
});
