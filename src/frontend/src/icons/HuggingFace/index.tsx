import React, { forwardRef } from "react";
import { ReactComponent as HugginFaceSVG } from "./hf-logo.svg";

export const HuggingFaceIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <HugginFaceSVG ref={ref} {...props} />;
});
