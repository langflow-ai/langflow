import React, { forwardRef } from "react";
import ShopifyIconSVG from "./shopify";

export const ShopifyIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ShopifyIconSVG ref={ref} {...props} />;
});