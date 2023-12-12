import React, { forwardRef } from "react";
import SvgShare2 from "./Share2";

export const Share2Icon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgShare2 ref={ref} {...props} />;
});
