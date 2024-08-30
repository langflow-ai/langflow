import React, { forwardRef } from "react";
import SvgUnstructured from "./Unstructured";

export const UnstructuredIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgUnstructured ref={ref} {...props} />;
});
