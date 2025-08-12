import React, { forwardRef } from "react";
import Google_AnalyticsIconSVG from "./google_analytics";

export const Google_AnalyticsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <Google_AnalyticsIconSVG ref={ref} {...props} />;
});