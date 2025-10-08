import type React from "react";
import { forwardRef } from "react";
import SvgSupabaseIcon from "./SupabaseIcon";

export const SupabaseIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSupabaseIcon ref={ref} {...props} />;
});
