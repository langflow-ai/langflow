import type React from "react";
import { forwardRef } from "react";
import SvgTeams from "./Teams";

type TeamsIconProps = React.SVGProps<SVGSVGElement> & { isDark?: boolean };

export const TeamsIcon = forwardRef<SVGSVGElement, TeamsIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgTeams ref={ref} {...props} />,
);
