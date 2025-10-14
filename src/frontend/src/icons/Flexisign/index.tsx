import React, { forwardRef } from "react";
import FlexisignIconSVG from "./flexisign";

export const FlexisignIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <FlexisignIconSVG ref={ref} {...props} />;
});
