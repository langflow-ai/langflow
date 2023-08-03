import React, { forwardRef } from "react";
import SvgSupabaseIcon from "./SupabaseIcon";

export const SupabaseIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSupabaseIcon ref={ref} {...props} />;
});
