import React, { forwardRef } from "react";
import LinearIconSVG from "./linear";

export const LinearIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <LinearIconSVG ref={ref} {...props} />;
});