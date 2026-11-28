import { forwardRef, type SVGProps } from "react";
import SvgKtemia from "./KtemiaIcon";

type KtemiaIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const KtemiaIcon = forwardRef<SVGSVGElement, KtemiaIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgKtemia ref={ref} {...props} />,
);
