import type React from "react";
import { forwardRef } from "react";
import SvgLiteLLM from "./LiteLLMIcon";

export const LiteLLMIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgLiteLLM ref={ref} {...props} />;
});
