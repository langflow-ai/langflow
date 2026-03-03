import React, { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";

import MergeIconSVG from "./MergeAgentHandlerIcon";

export const MergeIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <MergeIconSVG ref={ref} isdark={isdark} {...props} />;
});

MergeIcon.displayName = "MergeIcon";

// Backward-compatible export name.
export const MergeAgentHandlerIcon = MergeIcon;
