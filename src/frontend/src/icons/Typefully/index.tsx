import React, { forwardRef } from "react";
import TypefullyIconSVG from "./typefully";

export const TypefullyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <TypefullyIconSVG ref={ref} {...props} />;
});
