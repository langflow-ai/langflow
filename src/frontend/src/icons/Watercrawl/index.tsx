import React, { forwardRef } from "react";
import SvgWatercrawlLogo from "./WatercrawlLogo";

export const WatercrawlIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWatercrawlLogo ref={ref} {...props} />;
});
