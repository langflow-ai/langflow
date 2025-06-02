import React, { forwardRef } from "react";
import GooglemeetIconSVG from "./googlemeet";

export const GooglemeetIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GooglemeetIconSVG ref={ref} {...props} />;
});
