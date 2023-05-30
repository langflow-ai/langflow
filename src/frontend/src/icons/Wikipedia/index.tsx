import React, { forwardRef } from "react";
import { ReactComponent as WikipediaSVG } from "./Wikipedia.svg";

export const WikipediaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <WikipediaSVG ref={ref} {...props} />;
});
