import type React from "react";
import { forwardRef } from "react";
import SvgFamulor from "./FamulorIcon";

export const FamulorIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgFamulor ref={ref} {...props} />;
});
