import React, { forwardRef } from "react";
import { ReactComponent as OpenAiSVG } from "./openAI.svg";

export const OpenAiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <OpenAiSVG ref={ref} {...props} />;
});
