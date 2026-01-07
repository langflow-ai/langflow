import React, { forwardRef } from "react";
import CanvasIconSVG from "./canvas";

export const CanvasIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <CanvasIconSVG ref={ref} {...props} />;
});
