import type React from "react";
import { forwardRef } from "react";
import SvgSERPdive from "./SERPdive";

export const SERPdiveIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSERPdive ref={ref} {...props} />;
});
