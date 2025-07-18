import React, { forwardRef } from "react";
import SvgWatsonxAI from "./WatsonxAI";

export const WatsonxAiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWatsonxAI ref={ref} {...props} />;
});
