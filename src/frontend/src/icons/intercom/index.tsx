import React, { forwardRef } from "react";
import IntercomIconSVG from "./intercom";

export const IntercomIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <IntercomIconSVG ref={ref} {...props} />;
});