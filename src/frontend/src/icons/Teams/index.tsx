import type React from "react";
import { forwardRef } from "react";
import SvgTeams from "./Teams";

export const TeamsIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgTeams ref={ref} {...props} />;
  },
);
