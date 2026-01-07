import React, { forwardRef } from "react";
import SlidesIconSVG from "./slides";

export const SlidesIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SlidesIconSVG ref={ref} {...props} />;
});
