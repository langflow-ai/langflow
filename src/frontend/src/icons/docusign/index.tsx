import React, { forwardRef } from "react";
import DocusignIconSVG from "./docusign";

export const DocusignIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DocusignIconSVG ref={ref} {...props} />;
});