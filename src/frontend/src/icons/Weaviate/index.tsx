import React, { forwardRef } from "react";
import { ReactComponent as WeaviateSVG } from "./weaviate.svg";

export const WeaviateIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <WeaviateSVG ref={ref} {...props} />;
});
