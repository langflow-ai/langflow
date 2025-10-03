import React, { forwardRef } from "react";
import DigicertIconSVG from "./digicert";

export const DigicertIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DigicertIconSVG ref={ref} {...props} />;
});
