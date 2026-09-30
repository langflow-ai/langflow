import React, { forwardRef } from "react";
import SvgNovita from "./novita";

export const NovitaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgNovita ref={ref} {...props} />;
});
