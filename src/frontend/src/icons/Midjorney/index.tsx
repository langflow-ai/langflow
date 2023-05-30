import React, { forwardRef } from "react";
import { ReactComponent as MidjorneySVG } from "./Midjourney_Emblem.svg";

export const MidjorneyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <MidjorneySVG ref={ref} {...props} />;
});
