import type React from "react";
import { forwardRef } from "react";
import SvgOlostep from "./Olostep";

export const OlostepIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOlostep ref={ref} {...props} />;
});
