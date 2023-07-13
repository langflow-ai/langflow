import React, { forwardRef } from "react";
import SvgHfLogo from "./HfLogo";

export const HuggingFaceIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgHfLogo ref={ref} {...props} />;
});
