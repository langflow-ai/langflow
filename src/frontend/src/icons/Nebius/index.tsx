import React, { forwardRef } from "react";
import SvgNebius from "./nebius";

export const NebiusIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgNebius ref={ref} {...props} />;
});
