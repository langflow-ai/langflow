import type React from "react";
import { forwardRef } from "react";
import VolcengineSVG from "./VolcengineIcon";

export const VolcengineIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <VolcengineSVG ref={ref} {...props} />;
});
