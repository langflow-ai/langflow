import React, { forwardRef } from "react";
import { ReactComponent as HugginFaceSVG } from "./hf-logo.svg";

export const HugginFaceIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <HugginFaceSVG ref={ref} {...props} />;
});
