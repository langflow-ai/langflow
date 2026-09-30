import type React from "react";
import { forwardRef } from "react";
import SvgQDrant from "./QDrant";

export const QDrantIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgQDrant ref={ref} {...props} />;
});
