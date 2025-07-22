import type React from "react";
import { forwardRef } from "react";
import SvgVertexAi from "./VertexAi";

export const VertexAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgVertexAi ref={ref} {...props} />;
});
