import React, { forwardRef } from "react";
import SportsapiIconSVG from "./sportsapi";

export const SportsapiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SportsapiIconSVG ref={ref} {...props} />;
});
