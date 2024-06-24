import React, { forwardRef } from "react";
import SvgMistralIcon from "./mistralIcon";

export const MistralIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMistralIcon ref={ref} {...props} />;
});
