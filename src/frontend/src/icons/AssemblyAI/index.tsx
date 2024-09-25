import React, { forwardRef } from "react";
import AssemblyAISVG from "./AssemblyAI";

export const AssemblyAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AssemblyAISVG ref={ref} {...props} />;
});
