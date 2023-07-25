import React, { forwardRef } from "react";
import SvgAnthropicBox from "./AnthropicBox";

export const AnthropicIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAnthropicBox ref={ref} {...props} />;
});
