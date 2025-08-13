import type React from "react";
import { forwardRef } from "react";
import SvgGlobeOkIcon from "./globe-ok";

export const GlobeOkIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGlobeOkIcon ref={ref} {...props} />;
});
