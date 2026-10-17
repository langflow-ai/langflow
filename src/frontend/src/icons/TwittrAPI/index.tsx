import { forwardRef, type SVGProps } from "react";
import TwittrAPI from "./TwittrAPI";

type TwittrAPIIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const TwittrAPIIcon = forwardRef<SVGSVGElement, TwittrAPIIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <TwittrAPI ref={ref} {...props} />,
);
