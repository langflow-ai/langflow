import React, { forwardRef } from "react";
import SvgPineconeLogo from "./PineconeLogo";

export const PineconeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPineconeLogo ref={ref} {...props} />;
});
