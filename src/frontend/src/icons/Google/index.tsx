import React, { forwardRef } from "react";
import { ReactComponent as GoogleSVG } from "./google.svg";

export const GoogleIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GoogleSVG ref={ref} {...props} />;
});
