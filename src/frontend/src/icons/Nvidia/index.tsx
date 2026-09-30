import React, { forwardRef } from "react";
import NvidiaSVG from "./nvidia";

export const NvidiaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <NvidiaSVG ref={ref} {...props} />;
});
