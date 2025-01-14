import React, { forwardRef } from "react";
import Totogi from "./Totogi";

export const TotogiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <Totogi ref={ref} {...props} />;
});
