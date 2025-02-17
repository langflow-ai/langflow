import React, { forwardRef } from "react";
import SvgPotpie from "./Potpie";

export const PotpieIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPotpie ref={ref} {...props} />;
});
