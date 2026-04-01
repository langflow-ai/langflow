import React, { forwardRef } from "react";
import SvgWindsurf from "./Windsurf";

export const WindsurfIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWindsurf ref={ref} {...props} />;
});
