import type React from "react";
import { forwardRef } from "react";
import SvgDocling from "./Docling";

export const DoclingIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgDocling ref={ref} {...props} />;
});
