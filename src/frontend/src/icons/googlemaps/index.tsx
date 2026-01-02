import React, { forwardRef } from "react";
import GooglemapsIconSVG from "./googlemaps";

export const GooglemapsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GooglemapsIconSVG ref={ref} {...props} />;
});
