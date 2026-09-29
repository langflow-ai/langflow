import type React from "react";
import { forwardRef } from "react";
import SvgCheaperInference from "./CheaperInferenceIcon";

export const CheaperInferenceIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgCheaperInference ref={ref} {...props} />;
});
