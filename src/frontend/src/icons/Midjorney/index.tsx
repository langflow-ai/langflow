import type React from "react";
import { forwardRef } from "react";
import SvgMidjourneyEmblem from "./MidjourneyEmblem";

export const MidjourneyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMidjourneyEmblem ref={ref} {...props} />;
});
