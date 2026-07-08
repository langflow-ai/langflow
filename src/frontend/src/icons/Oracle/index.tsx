import type React from "react";
import { forwardRef } from "react";
import SvgOracle from "./Oracle";

export const OracleIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOracle ref={ref} {...props} />;
});
