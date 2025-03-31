import React, { forwardRef } from "react";
import SvgNeedleIcon from "./NeedleIcon";

export const NeedleIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgNeedleIcon ref={ref} {...props} />;
});
