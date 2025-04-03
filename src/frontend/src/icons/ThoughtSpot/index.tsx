import React, { forwardRef } from "react";
import SvgThoughtSpot from "./ThoughtSpot";

export const ThoughtSpotIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgThoughtSpot ref={ref} {...props} />;
});
