import { render } from "@testing-library/react";
import { createRef } from "react";

// The svg itself lives in FigraniumIcon.jsx, which the Jest transform does not
// compile; stub it so the wrapper's ref forwarding and prop passthrough are what
// this test exercises.
jest.mock("../FigraniumIcon", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      React.createElement("svg", { "data-testid": "figranium-svg", ...props }),
  };
});

import { FigraniumIcon } from "../index";

describe("FigraniumIcon", () => {
  it("forwards the ref and props to the svg component", () => {
    const ref = createRef<SVGSVGElement>();
    const { getByTestId } = render(
      <FigraniumIcon ref={ref} className="h-4 w-4" aria-label="Figranium" />,
    );

    const svg = getByTestId("figranium-svg");
    expect(svg).toHaveClass("h-4", "w-4");
    expect(svg).toHaveAttribute("aria-label", "Figranium");
    expect(ref.current).toBe(svg);
  });
});
