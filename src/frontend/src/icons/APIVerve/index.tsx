import type React from "react";
import { forwardRef } from "react";
import SvgAPIVerve from "./APIVerveIcon";

export const APIVerveIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgAPIVerve ref={ref} {...props} />;
});
