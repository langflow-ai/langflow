import React, { forwardRef } from "react";
import { ReactComponent as SerperSVG } from "./serper.svg";

export const SerperIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SerperSVG ref={ref} {...props} />;
});
