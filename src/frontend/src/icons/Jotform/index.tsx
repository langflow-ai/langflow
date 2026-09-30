import React, { forwardRef } from "react";
import JotformIconSVG from "./jotform";

export const JotformIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <JotformIconSVG ref={ref} {...props} />;
});
