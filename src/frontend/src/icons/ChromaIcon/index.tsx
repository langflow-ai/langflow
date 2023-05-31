import React, { forwardRef } from "react";
import { ReactComponent as ChromaSVG } from "./chroma.svg";

export const ChromaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ChromaSVG ref={ref} {...props} />;
});
