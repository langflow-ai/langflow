import React, { forwardRef } from "react";
import SvgElasticsearchLogo from "./ElasticsearchLogo";

export const ElasticsearchIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgElasticsearchLogo ref={ref} {...props} />;
});
