import React, { forwardRef } from "react";
import JiraIconSVG from "./jira";

export const JiraIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <JiraIconSVG ref={ref} {...props} />;
  },
);
