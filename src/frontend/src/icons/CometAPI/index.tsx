import type React from "react";
import { forwardRef } from "react";
import SvgCometAPI from "./cometapi";

export const CometAPIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCometAPI ref={ref} {...props} />;
});
