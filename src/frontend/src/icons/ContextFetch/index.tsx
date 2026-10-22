import type React from "react";
import { forwardRef } from "react";
import SvgContextFetch from "./ContextFetch";

export const ContextFetchIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgContextFetch ref={ref} {...props} />;
});
