import React, { forwardRef } from "react";
import JiraSvgIcon from "./jira";

export const JiraIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <JiraSvgIcon ref={ref} {...props} />;
});
