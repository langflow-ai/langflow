import type React from "react";
import { forwardRef } from "react";
import DiscordIconSVG from "./discord";

type DiscordIconProps = React.SVGProps<SVGSVGElement> & { isDark?: boolean };

export const DiscordIcon = forwardRef<SVGSVGElement, DiscordIconProps>(
  ({ isDark: _isDark, ...props }, ref) => (
    <DiscordIconSVG ref={ref} {...props} />
  ),
);
