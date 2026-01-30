import type React from "react";
import { forwardRef } from "react";
import SvgAgentics from "./Agentics";

export const AgenticsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAgentics ref={ref} {...props} />;
});
