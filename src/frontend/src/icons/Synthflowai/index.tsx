import React, { forwardRef } from "react";
import SynthflowaiIconSVG from "./synthflowai";

export const SynthflowaiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SynthflowaiIconSVG ref={ref} {...props} />;
});
