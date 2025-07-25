import type React from "react";
import { forwardRef } from "react";
import SvgMaritalkIcon from "./MaritalkIcon";

export const MaritalkIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMaritalkIcon ref={ref} {...props} />;
});
