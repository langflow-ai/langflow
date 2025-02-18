import React, { forwardRef } from "react";
import SvgCrateDBIcon from "./CrateDB";

export const CrateDBIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCrateDBIcon ref={ref} {...props} />;
});
