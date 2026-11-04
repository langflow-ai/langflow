import { render } from "@testing-library/react";
import { createRef } from "react";

// The svg itself lives in FamulorIcon.jsx, which the Jest transform does not
// compile; stub it so the wrapper's ref forwarding and prop passthrough are what
// this test exercises.
jest.mock("../FamulorIcon", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      React.createElement("svg", { "data-testid": "famulor-svg", ...props }),
  };
});

import { FamulorIcon } from "../index";

describe("FamulorIcon", () => {
  it("forwards the ref and props to the svg component", () => {
    const ref = createRef<SVGSVGElement>();
    const { getByTestId } = render(
      <FamulorIcon ref={ref} className="h-4 w-4" aria-label="Famulor" />,
    );

    const svg = getByTestId("famulor-svg");
    expect(svg).toHaveClass("h-4", "w-4");
    expect(svg).toHaveAttribute("aria-label", "Famulor");
    expect(ref.current).toBe(svg);
  });
});
