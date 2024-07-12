import React, { forwardRef } from "react";
import SvgPython from "./Python";

export const PythonIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPython ref={ref} {...props} />;
});
