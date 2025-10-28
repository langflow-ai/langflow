import type React from "react";
import { forwardRef } from "react";
import SvgHelicone from "./HeliconeIcon";

export const HeliconeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgHelicone ref={ref} {...props} />;
});
