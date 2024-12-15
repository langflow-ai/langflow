import React, { forwardRef } from "react";
import SvgWoolBall from "./WoolBall";

export const WoolBallIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWoolBall ref={ref} {...props} />;
});