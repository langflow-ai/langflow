import type React from "react";
import { forwardRef } from "react";
import SvgSearchHybridIcon from "./SearchHybridIcon";

export const SearchHybridIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSearchHybridIcon ref={ref} {...props} />;
});
