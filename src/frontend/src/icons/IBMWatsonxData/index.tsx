import React, { forwardRef } from "react";
import SvgWatsonxData from "./WatsonxData";

export const WatsonxDataIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWatsonxData ref={ref} {...props} />;
});
