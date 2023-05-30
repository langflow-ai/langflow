import React, { forwardRef } from "react";
import { ReactComponent as WolframSVG } from "./wolfram.svg";

export const WolframIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <WolframSVG ref={ref} {...props} />;
});
