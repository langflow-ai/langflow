import type React from "react";
import { forwardRef } from "react";
import SvgMailtrap from "./Mailtrap";

type MailtrapIconProps = React.SVGProps<SVGSVGElement> & { isDark?: boolean };

export const MailtrapIcon = forwardRef<SVGSVGElement, MailtrapIconProps>(
  (props, ref) => <SvgMailtrap ref={ref} {...props} />,
);
