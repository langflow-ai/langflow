import React, { forwardRef } from "react";
import SvgVectaraIcon from "./VectaraIcon";

export const VectaraIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgVectaraIcon className="icon" ref={ref} {...props} />;
});
