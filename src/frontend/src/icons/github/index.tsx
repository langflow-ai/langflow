import type React from "react";
import { forwardRef } from "react";
import GithubIconSVG from "./github";

type GithubIconProps = React.SVGProps<SVGSVGElement> & { isDark?: boolean };

export const GithubIcon = forwardRef<SVGSVGElement, GithubIconProps>(
  ({ isDark: _isDark, ...props }, ref) => (
    <GithubIconSVG ref={ref} {...props} />
  ),
);
