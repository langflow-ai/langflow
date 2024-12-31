import React, { forwardRef } from "react";
import SvgNotDiamondIcon from "./NotDiamondIcon";

export const NotDiamondIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgNotDiamondIcon ref={ref} {...props} />;
});
