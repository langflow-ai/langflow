import type React from "react";
import { forwardRef } from "react";
import SvgEmpirioLabs from "./empiriolabs";

export const EmpirioLabsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgEmpirioLabs ref={ref} {...props} />;
});
