import React, { forwardRef } from "react";
import SvgSearchVectorIcon from "./SearchVectorIcon";

export const SearchVectorIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgSearchVectorIcon ref={ref} {...props} />;
});
