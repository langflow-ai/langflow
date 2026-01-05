import React, { forwardRef } from "react";
import TwitterXSVG from "./TwitterX.jsx";

export const TwitterXIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <TwitterXSVG ref={ref} {...props} />;
});
