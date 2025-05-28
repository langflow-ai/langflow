import React, { forwardRef } from "react";
import SvgMilvus from "./Milvus";

export const MilvusIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMilvus ref={ref} {...props} />;
});
