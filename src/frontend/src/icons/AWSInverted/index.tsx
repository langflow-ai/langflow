import type React from "react";
import { forwardRef } from "react";
import SvgAWS from "./AWS";

export const AWSInvertedIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAWS ref={ref} {...props} />;
});
