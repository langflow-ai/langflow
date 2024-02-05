import React, { forwardRef } from "react";
import SvgVectara from "./Vectara";

export const VectaraIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgVectara className="icon" ref={ref} {...props} />;
});
