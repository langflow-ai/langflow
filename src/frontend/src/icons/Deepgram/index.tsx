import React, { forwardRef } from "react";
import DeepgramIconSVG from "./deepgram";

export const DeepgramIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DeepgramIconSVG ref={ref} {...props} />;
});
