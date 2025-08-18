import type React from "react";
import { forwardRef } from "react";
import SvgConfluence from "./Confluence";

export const ConfluenceIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgConfluence ref={ref} {...props} />;
});
