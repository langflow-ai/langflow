import type React from "react";
import { forwardRef } from "react";
import GigaChatSVG from "./GigaChatIcon";

export const GigaChatIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GigaChatSVG ref={ref} {...props} />;
});
