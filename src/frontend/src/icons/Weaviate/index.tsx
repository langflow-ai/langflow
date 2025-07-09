import type React from "react";
import { forwardRef } from "react";
import SvgWeaviate from "./Weaviate";

export const WeaviateIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWeaviate ref={ref} {...props} />;
});
