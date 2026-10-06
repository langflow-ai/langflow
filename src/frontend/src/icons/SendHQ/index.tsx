import { forwardRef, type SVGProps } from "react";
import SendHQ from "./SendHQ";

type SendHQIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const SendHQIcon = forwardRef<SVGSVGElement, SendHQIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SendHQ ref={ref} {...props} />,
);
