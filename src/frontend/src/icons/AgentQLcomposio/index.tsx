import React, { forwardRef } from "react";
import AgentqlIconSVG from "./agentql";

export const AgentqlIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AgentqlIconSVG ref={ref} {...props} />;
});
