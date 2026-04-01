import React, { forwardRef } from "react";
import AgiledIconSVG from "./agiled";

export const AgiledIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AgiledIconSVG ref={ref} {...props} />;
});
