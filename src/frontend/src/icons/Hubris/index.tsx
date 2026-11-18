import React, { forwardRef } from "react";
import SvgHubris from "./hubris";

export const HubrisIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgHubris ref={ref} {...props} />;
});
