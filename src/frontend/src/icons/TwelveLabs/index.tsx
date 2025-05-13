import React, { forwardRef } from "react";
import SvgTwelveLogo from "./TwelveLabsLogo";

export const TwelveLabsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgTwelveLogo ref={ref} {...props} />;
});
