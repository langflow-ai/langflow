import type React from "react";
import { forwardRef } from "react";
import SvgAPIRoute from "./APIRouteIcon";

export const APIRouteIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAPIRoute ref={ref} {...props} />;
});
