import React, { forwardRef } from "react";
import Icon from "./microsoft_teams";

export const Microsoft_TeamsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <Icon ref={ref} {...props} />;
});
