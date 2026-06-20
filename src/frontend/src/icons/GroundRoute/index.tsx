import type React from "react";
import { forwardRef } from "react";
import GroundRoute from "./GroundRouteIcon";

export const GroundRouteIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GroundRoute ref={ref} {...props} />;
});
