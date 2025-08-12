import React, { forwardRef } from "react";
import HubspotIconSVG from "./hubspot";

export const HubspotIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <HubspotIconSVG ref={ref} {...props} />;
});