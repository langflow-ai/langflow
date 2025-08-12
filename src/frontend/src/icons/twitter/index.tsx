import React, { forwardRef } from "react";
import TwitterIconSVG from "./twitter";

export const TwitterIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <TwitterIconSVG ref={ref} {...props} />;
});