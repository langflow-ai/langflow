import type React from "react";
import { forwardRef } from "react";
import SvgAgentGuild from "./AgentGuildIcon";

export const AgentGuildIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement>
>((props, ref) => <SvgAgentGuild ref={ref} {...props} />);
