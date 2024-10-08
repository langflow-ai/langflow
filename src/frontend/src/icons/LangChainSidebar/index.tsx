import React, { forwardRef } from "react";
import SvgLangChainIconSidebar from "./LangChainIconSidebar";

export const LangChainIconSidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgLangChainIconSidebar ref={ref} {...props} />;
});
