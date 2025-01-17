import React, { forwardRef } from "react";
import SvgOlivya from "./Olivya";

export const OlivyaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOlivya ref={ref} {...props} />;
});
