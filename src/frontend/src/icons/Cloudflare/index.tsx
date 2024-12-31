import React, { forwardRef } from "react";
import SvgCloudflareIcon from "./Cloudflare";

export const CloudflareIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCloudflareIcon ref={ref} {...props} />;
});
