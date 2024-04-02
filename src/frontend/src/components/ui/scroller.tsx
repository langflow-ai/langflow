import { OverlayScrollbarsComponent } from "overlayscrollbars-react";
import React from "react";
import { useDarkStore } from "../../stores/darkStore";

const Scroller = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ children, ...props }, ref) => {
  const dark = useDarkStore((state) => state.dark);
  return (
    <OverlayScrollbarsComponent
      defer
      options={{
        scrollbars: {
          autoHide: "scroll",
          theme: dark ? "os-theme-dark" : "os-theme-light",
        },
      }}
      {...props}
    >
      {children}
    </OverlayScrollbarsComponent>
  );
});

export default Scroller;
