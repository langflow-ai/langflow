import React, { forwardRef } from "react";
import FinageIconSVG from "./finage";

export const FinageIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <FinageIconSVG ref={ref} {...props} />;
});
