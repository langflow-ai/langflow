import React, { forwardRef } from "react";
import SvgIcon from "./Tongyi";

export const TongyiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgIcon ref={ref} {...props} />;
});
