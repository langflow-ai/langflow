import React, { forwardRef } from "react";
import MondayIconSVG from "./monday";

export const MondayIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <MondayIconSVG ref={ref} {...props} />;
});
