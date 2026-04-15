import React, { forwardRef } from "react";
import SvgMengram from "./SvgMengram";

export const MengramIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMengram className="icon" ref={ref} {...props} />;
});
