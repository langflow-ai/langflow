import React, { forwardRef } from "react";
import AstraSVG from "./AstraDB";

export const AstraDBIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AstraSVG ref={ref} {...props} />;
});
