import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgMcpIcon from "./McpIcon";

export const McpIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isdark = useDarkStore((state) => state.dark);
    return <SvgMcpIcon ref={ref} isdark={isdark} {...props} />;
  },
);
