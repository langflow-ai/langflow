import type React from "react";
import { forwardRef } from "react";
import SvgAstraflow from "./AstraflowIcon";

export const AstraflowIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAstraflow ref={ref} {...props} />;
});
