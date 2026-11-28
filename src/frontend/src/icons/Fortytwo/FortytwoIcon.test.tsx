import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { FortytwoIcon } from ".";

it.each([false, true])(
  "forwards SVG props and ref without leaking isDark=%s",
  (isDark) => {
    const ref = createRef<SVGSVGElement>();
    const error = jest.spyOn(console, "error").mockImplementation(() => {});
    try {
      render(
        <FortytwoIcon
          ref={ref}
          isDark={isDark}
          aria-label="Fortytwo"
          role="img"
          className="provider-icon"
          width={24}
        />,
      );
      const icon = screen.getByRole("img", { name: "Fortytwo" });
      expect(ref.current).toBe(icon);
      expect(icon).toHaveAttribute("width", "24");
      expect(icon).toHaveClass("provider-icon");
      expect(icon).not.toHaveAttribute("isDark");
      expect(error).not.toHaveBeenCalled();
    } finally {
      error.mockRestore();
    }
  },
);
