import React, { forwardRef } from "react";
import SvgGoogleGenerativeAI from "./GoogleGemini";

export const GoogleGenerativeAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGoogleGenerativeAI ref={ref} {...props} />;
});
