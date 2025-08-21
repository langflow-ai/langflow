import React, { forwardRef } from "react";
import SvgVectorStores from "./vectorstores";

export const VectorStoresIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgVectorStores ref={ref} {...props} />;
});
