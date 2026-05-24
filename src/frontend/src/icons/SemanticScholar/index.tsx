import React, { forwardRef } from "react";
import SemanticScholarIconSVG from "./SemanticScholarIcon.jsx";

export const SemanticScholarIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SemanticScholarIconSVG ref={ref} {...props} />;
});

export default SemanticScholarIcon;
