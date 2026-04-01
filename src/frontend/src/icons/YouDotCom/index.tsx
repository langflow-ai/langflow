import type React from "react";
import { forwardRef } from "react";
import YouDotCom from "./YouDotCom";

export const YouDotComIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <YouDotCom ref={ref} {...props} />;
});
