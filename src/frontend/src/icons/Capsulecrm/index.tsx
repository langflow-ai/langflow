import React, { forwardRef } from "react";
import CapsulecrmIconSVG from "./capsulecrm";

export const CapsulecrmIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <CapsulecrmIconSVG ref={ref} {...props} />;
});
