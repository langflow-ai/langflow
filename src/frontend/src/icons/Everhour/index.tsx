import React, { forwardRef } from "react";
import EverhourIconSVG from "./everhour";

export const EverhourIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <EverhourIconSVG ref={ref} {...props} />;
});
