import React, { forwardRef } from "react";
import MissiveIconSVG from "./missive";

export const MissiveIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <MissiveIconSVG ref={ref} {...props} />;
});
