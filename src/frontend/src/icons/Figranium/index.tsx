import type React from "react";
import { forwardRef } from "react";
import SvgFigranium from "./FigraniumIcon";

export const FigraniumIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgFigranium ref={ref} {...props} />;
});
