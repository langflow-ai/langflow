import type React from "react";
import { forwardRef } from "react";
import SvgHumanInput from "./HumanInput";

export const HumanInputIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgHumanInput ref={ref} {...props} />;
});
