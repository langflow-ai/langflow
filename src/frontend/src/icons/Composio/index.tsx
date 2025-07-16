import React, { forwardRef } from "react";
import ComposioIconSVG from "./composio";

export const ComposioIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ComposioIconSVG ref={ref} {...props} />;
});
