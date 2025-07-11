import type React from "react";
import { forwardRef } from "react";
import SvgSambaNovaLogo from "./SambaNovaLogo";

export const SambaNovaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSambaNovaLogo ref={ref} {...props} />;
});
