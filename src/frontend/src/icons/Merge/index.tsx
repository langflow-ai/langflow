import React, { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";

import MergeIconSVG from "./MergeAgentHandlerIcon";

export const MergeIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isDark = useDarkStore((state) => state.dark);
    return <MergeIconSVG ref={ref} isDark={isDark} {...props} />;
  },
);

MergeIcon.displayName = "MergeIcon";

// Backward-compatible export name.
export const MergeAgentHandlerIcon = MergeIcon;
