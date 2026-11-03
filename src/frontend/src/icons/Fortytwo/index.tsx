import type React from "react";
import { forwardRef } from "react";
import SvgFortytwo from "./FortytwoIcon";

export const FortytwoIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgFortytwo ref={ref} {...props} />;
});
