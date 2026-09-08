import type React from "react";
import { forwardRef } from "react";
import Context from "./ContextIcon";

export const ContextIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <Context ref={ref} {...props} />;
});
