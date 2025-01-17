import React, { forwardRef } from "react";
import SvgCsgLogo from "./Csg"

export const CsgIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCsgLogo ref={ref} {...props} />;
});
