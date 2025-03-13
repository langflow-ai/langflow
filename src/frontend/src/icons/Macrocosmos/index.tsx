import React, { forwardRef } from "react";
import SvgMacrocosmos from "./MacrocosmosLogo";

export const MacrocosmosIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMacrocosmos ref={ref} {...props} />;
});
