import React, { forwardRef } from "react";
import ContentfulIconSVG from "./contentful";

export const ContentfulIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ContentfulIconSVG ref={ref} {...props} />;
});
