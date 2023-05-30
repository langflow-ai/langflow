import React, { forwardRef } from "react";
import { ReactComponent as GitBookSVG } from "./gitbook-svgrepo-com.svg";

export const GitBookIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <GitBookSVG ref={ref} {...props} />;
});
