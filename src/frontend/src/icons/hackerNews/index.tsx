import React, { forwardRef } from "react";
import SvgYCombinatorLogo from "./YCombinatorLogo";

export const HackerNewsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgYCombinatorLogo ref={ref} {...props} />;
});
