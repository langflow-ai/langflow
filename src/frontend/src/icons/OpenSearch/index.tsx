import type React from "react";
import { forwardRef } from "react";
import OpenSearchSVG from "./OpenSearch";

export const OpenSearch = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <OpenSearchSVG ref={ref} {...props} />;
});
