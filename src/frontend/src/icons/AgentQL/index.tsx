import type React from "react";
import { forwardRef } from "react";
import SvgAgentQL from "./AgentQL";

export const AgentQLIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAgentQL ref={ref} {...props} />;
});
