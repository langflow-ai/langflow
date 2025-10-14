import React, { forwardRef } from "react";
import OpenAIIconSVG from "./openai";

export const OpenAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <OpenAIIconSVG ref={ref} {...props} />;
});
