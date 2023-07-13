import React, { forwardRef } from "react";
import SvgGoogle from "./Google";

export const GoogleIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGoogle ref={ref} {...props} />;
});
