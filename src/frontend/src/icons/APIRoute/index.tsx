import type React from "react";
import { forwardRef } from "react";
import SvgAPIRoute from "./APIRouteIcon";

export const APIRouteIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ isDark?: boolean }>
>((props, ref) => {
  return <SvgAPIRoute ref={ref} {...props} />;
});
