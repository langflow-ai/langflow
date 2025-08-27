import type React from "react";
import { forwardRef } from "react";
import SvgMistralIcon from "./mistralIcon";

export const MistralIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMistralIcon ref={ref} {...props} />;
});
