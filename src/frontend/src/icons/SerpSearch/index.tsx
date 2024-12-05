import React, { forwardRef } from "react";
import SvgSerpSearchAPI from "./SerpSearch";

export const SerpSearchIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSerpSearchAPI ref={ref} {...props} />;
});
