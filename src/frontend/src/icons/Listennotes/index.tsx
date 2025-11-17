import React, { forwardRef } from "react";
import ListennotesIconSVG from "./listennotes";

export const ListennotesIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ListennotesIconSVG ref={ref} {...props} />;
});
