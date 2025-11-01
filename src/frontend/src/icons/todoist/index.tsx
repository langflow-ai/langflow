import React, { forwardRef } from "react";
import TodoistIconSVG from "./todoist";

export const TodoistIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return (
    <span
      style={{
        display: "inline-grid",
        width: 22,
        height: 22,
        placeItems: "center",
        flexShrink: 0,
      }}
    >
      <TodoistIconSVG ref={ref} {...props} />
    </span>
  );
});
