import React, { forwardRef } from "react";
import SvgCrewAISidebar from "./CrewAISidebar";

export const CrewAISidebar = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgCrewAISidebar ref={ref} {...props} />;
});
