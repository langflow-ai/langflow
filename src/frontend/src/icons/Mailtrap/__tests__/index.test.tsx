import { render } from "@testing-library/react";
import { createRef } from "react";

// The svg itself lives in Mailtrap.jsx, which the Jest transform does not
// compile; stub it so the wrapper's ref forwarding and prop passthrough are what
// this test exercises.
jest.mock("../Mailtrap", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: ({ isDark, ...props }: Record<string, unknown>) =>
      React.createElement("svg", {
        "data-testid": "mailtrap-svg",
        "data-dark": String(isDark),
        ...props,
      }),
  };
});

import { MailtrapIcon } from "../index";

describe("MailtrapIcon", () => {
  it("forwards the ref and props to the svg component", () => {
    const ref = createRef<SVGSVGElement>();
    const { getByTestId } = render(
      <MailtrapIcon ref={ref} className="h-4 w-4" aria-label="Mailtrap" />,
    );

    const svg = getByTestId("mailtrap-svg");
    expect(svg).toHaveClass("h-4", "w-4");
    expect(svg).toHaveAttribute("aria-label", "Mailtrap");
    expect(ref.current).toBe(svg);
  });

  it("passes isDark through so the mark can switch colors", () => {
    const { getByTestId } = render(<MailtrapIcon isDark />);

    expect(getByTestId("mailtrap-svg")).toHaveAttribute("data-dark", "true");
  });
});
