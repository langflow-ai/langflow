import React, { forwardRef } from "react";
import LemlistIconSVG from "./lemlist";

export const LemlistIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <LemlistIconSVG ref={ref} {...props} />;
});
