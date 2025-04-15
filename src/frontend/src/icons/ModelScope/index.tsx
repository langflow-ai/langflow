import React, { forwardRef } from "react";
import SvgModelScope from "./ModelScope";

export const ModelScopeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgModelScope ref={ref} {...props} />;
});
