import React, { forwardRef } from "react";
import SvgSearchHybridIcon from "./SearchHybridIcon";

export const SearchHybridIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSearchHybridIcon ref={ref} {...props} />;
});
