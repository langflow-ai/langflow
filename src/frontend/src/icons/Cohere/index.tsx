import React, { forwardRef } from "react";
import SvgCohere from "./Cohere";

export const CohereIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCohere ref={ref} {...props} />;
});
