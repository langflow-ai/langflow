import type React from "react";
import { forwardRef } from "react";
import SvgGeekflareLogo from "./GeekflareLogo";

export const GeekflareIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgGeekflareLogo ref={ref} {...props} />;
});

GeekflareIcon.displayName = "GeekflareIcon";
