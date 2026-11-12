import { forwardRef, type SVGProps } from "react";
import TurboNotify from "./TurboNotify";

type TurboNotifyIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const TurboNotifyIcon = forwardRef<SVGSVGElement, TurboNotifyIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <TurboNotify ref={ref} {...props} />,
);
