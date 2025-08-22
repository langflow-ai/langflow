import React, { forwardRef } from "react";
import SalesforceIconSVG from "./salesforce";

export const SalesforceIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SalesforceIconSVG ref={ref} {...props} />;
});
