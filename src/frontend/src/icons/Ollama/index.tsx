import React, { forwardRef } from "react";
import SvgOllama from "./Ollama";

export const OllamaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOllama ref={ref} {...props} />;
});
