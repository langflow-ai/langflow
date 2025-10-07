import type React from "react";
import { forwardRef } from "react";
import SvgSerper from "./Serper";

export const SerperIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSerper ref={ref} {...props} />;
});
