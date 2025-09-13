import React, { forwardRef } from "react";
import CalendlyIconSVG from "./calendly";

export const CalendlyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <CalendlyIconSVG ref={ref} {...props} />;
});
