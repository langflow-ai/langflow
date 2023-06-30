import React, { forwardRef } from "react";
import { ReactComponent as VertexAISVG } from "./vertex_ai.svg";

export const VertexAIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <VertexAISVG ref={ref} {...props} />;
});
