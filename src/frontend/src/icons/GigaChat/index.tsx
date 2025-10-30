import React, { forwardRef } from "react";
import GigaChatIconSVG from "./GigaChat";

export const GigaChatIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GigaChatIconSVG ref={ref} {...props} />;
});
