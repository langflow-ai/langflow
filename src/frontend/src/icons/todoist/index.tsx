import React, { forwardRef } from "react";
import TodoistIconSVG from "./todoist";

export const TodoistIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <TodoistIconSVG ref={ref} {...props} />;
});