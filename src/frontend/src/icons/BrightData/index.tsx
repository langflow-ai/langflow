import React, { forwardRef } from "react";
import SvgBrightData from "./BrightData";

export const BrightDataIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement>
>((props, ref) => {
  return <SvgBrightData ref={ref} {...props} />;
});

BrightDataIcon.displayName = "BrightDataIcon";