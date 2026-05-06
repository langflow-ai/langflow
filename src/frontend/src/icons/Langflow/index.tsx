import type React from "react";
import { forwardRef } from "react";
import SvgLangflowIcon from "./LangflowIcon";

export const LangflowIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgLangflowIcon ref={ref} {...props} />;
});
