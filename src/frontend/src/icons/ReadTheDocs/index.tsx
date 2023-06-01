import React, { forwardRef } from "react";
import { ReactComponent as ReadTheDocsSVG } from "./readthedocsio-icon.svg";

export const ReadTheDocsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ReadTheDocsSVG ref={ref} {...props} />;
});
