import React, { forwardRef } from "react";
import { ReactComponent as CohereSVG } from "./cohere.svg";

export const CohereIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <CohereSVG ref={ref} {...props} />;
});
