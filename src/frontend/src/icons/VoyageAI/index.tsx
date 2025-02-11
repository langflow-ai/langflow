import React, { forwardRef } from "react";
import SvgVoyageAI from "./VoyageAI";

export const VoyageAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgVoyageAI className="icon" ref={ref} {...props} />;
});
