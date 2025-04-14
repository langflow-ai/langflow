import React, { forwardRef } from "react";
import SvgTessAIIcon from "./tessAIIcon";

export const TessAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgTessAIIcon ref={ref} {...props} />;
});
