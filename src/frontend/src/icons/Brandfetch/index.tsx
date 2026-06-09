import React, { forwardRef } from "react";
import BrandfetchIconSVG from "./brandfetch";

export const BrandfetchIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <BrandfetchIconSVG ref={ref} {...props} />;
});
