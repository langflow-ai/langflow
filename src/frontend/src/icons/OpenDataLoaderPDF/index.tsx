import type React from "react";
import { forwardRef } from "react";
import SvgOpenDataLoaderPDF from "./OpenDataLoaderPDF";

export const OpenDataLoaderPDFIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgOpenDataLoaderPDF ref={ref} {...props} />;
});
