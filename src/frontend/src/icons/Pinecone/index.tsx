import React, { forwardRef } from "react";
import { ReactComponent as PineconeSVG } from "./pinecone_logo.svg";

export const PineconeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <PineconeSVG ref={ref} {...props} />;
});
