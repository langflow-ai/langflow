import React, { forwardRef } from "react";
import GoogledocsIconSVG from "./googledocs";

export const GoogledocsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GoogledocsIconSVG ref={ref} {...props} />;
});
