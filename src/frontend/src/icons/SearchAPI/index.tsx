import React, { forwardRef } from "react";
import SvgSearchApi from "./SearchAPI";

export const SearchAPIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSearchApi ref={ref} {...props} />;
});
