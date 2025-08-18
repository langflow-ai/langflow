import type React from "react";
import { forwardRef } from "react";
import BWSvgPython from "./Python";

export const BWPythonIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <BWSvgPython ref={ref} {...props} />;
});
