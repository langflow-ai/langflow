import React, { forwardRef } from "react";
import SvgGigaChat from "./GigaChat";

export const GigaChatIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGigaChat ref={ref} {...props} />;
});
